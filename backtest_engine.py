"""
バックテストエンジン - トレーディングロジックの検証用
過去データで戦略をシミュレーションし、パフォーマンスを測定
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime
from services.data_service import DataService
from services.optimized_trading_logic import OptimizedTradingLogic
from services.enhanced_trading_logic import EnhancedTradingLogic

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    バックテストエンジン

    機能:
    1. 過去データでの戦略シミュレーション
    2. パフォーマンスメトリクス計算（勝率、PF、シャープレシオ等）
    3. 詳細な取引履歴出力
    4. 複数戦略の比較
    """

    def __init__(self, initial_capital=10000, commission_rate=0.0001):
        """
        初期化

        Args:
            initial_capital: 初期資金（円）
            commission_rate: 手数料率（0.01% = 0.0001）
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.trades = []
        self.equity_curve = []

    def run_backtest(self, df, trading_logic, symbol="DOGE_JPY"):
        """
        バックテスト実行

        Args:
            df: 過去データのDataFrame（OHLCVとインジケーター付き）
            trading_logic: トレーディングロジックのインスタンス
            symbol: 取引シンボル

        Returns:
            バックテスト結果の辞書
        """
        logger.info(f"="*60)
        logger.info(f"Starting Backtest: {symbol}")
        logger.info(f"Data: {len(df)} candles from {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        logger.info(f"Initial Capital: ¥{self.initial_capital:,.0f}")
        logger.info(f"="*60)

        # 初期化
        capital = self.initial_capital
        position = None  # {'type': 'BUY'|'SELL', 'entry_price': float, 'size': float, 'entry_time': datetime}
        self.trades = []
        self.equity_curve = []

        # 各ローソク足で取引判定
        for i in range(50, len(df)):  # 最初の50本はインジケーター計算用にスキップ
            current_candle = df.iloc[i]
            current_price = current_candle['close']
            current_time = current_candle['timestamp']

            # 過去データを渡す（マルチタイムフレーム分析用）
            historical_df = df.iloc[:i+1]

            # エクイティ記録
            if position:
                # ポジション保有中の評価額
                if position['type'] == 'BUY':
                    unrealized_pnl = (current_price - position['entry_price']) * position['size']
                else:  # SELL
                    unrealized_pnl = (position['entry_price'] - current_price) * position['size']

                current_equity = capital + unrealized_pnl
            else:
                current_equity = capital

            self.equity_curve.append({
                'timestamp': current_time,
                'equity': current_equity,
                'capital': capital,
                'position': position['type'] if position else None
            })

            # ポジション保有中の決済チェック
            if position:
                should_close = self._check_close_position(
                    position, current_price, current_candle.to_dict(), trading_logic
                )

                if should_close:
                    # 決済実行
                    trade_result = self._close_position(position, current_price, current_time, capital)
                    self.trades.append(trade_result)

                    capital = trade_result['exit_capital']
                    position = None

                    logger.info(f"[{current_time}] Close: {trade_result['type']} @ ¥{current_price:.2f} | "
                               f"P/L: ¥{trade_result['pnl']:.2f} ({trade_result['pnl_pct']:.2f}%)")

                continue  # ポジション決済後は新規エントリーしない

            # 新規エントリーシグナルチェック
            market_data = current_candle.to_dict()

            should_trade, trade_type, reason, confidence, stop_loss, take_profit = trading_logic.should_trade(
                market_data, historical_df
            )

            if should_trade and trade_type and confidence >= 1.2:  # 最低信頼度1.2
                # 新規ポジションエントリー
                position = self._open_position(
                    trade_type, current_price, current_time, capital, stop_loss, take_profit
                )

                logger.info(f"[{current_time}] Open: {trade_type} @ ¥{current_price:.2f} | "
                           f"Confidence: {confidence:.2f} | Reason: {reason}")
                logger.info(f"   SL: ¥{stop_loss:.2f}, TP: ¥{take_profit:.2f}")

        # 最終ポジションがあれば決済
        if position:
            final_price = df.iloc[-1]['close']
            final_time = df.iloc[-1]['timestamp']
            trade_result = self._close_position(position, final_price, final_time, capital)
            self.trades.append(trade_result)
            capital = trade_result['exit_capital']

        # パフォーマンス計算
        performance = self._calculate_performance(capital)

        logger.info(f"\n" + "="*60)
        logger.info(f"Backtest Completed")
        logger.info(f"="*60)
        self._print_performance(performance)

        return performance

    def _open_position(self, trade_type, entry_price, entry_time, capital, stop_loss, take_profit):
        """ポジションオープン"""
        # ポジションサイズ計算（資金の95%）
        available = capital * 0.95
        size = available / entry_price

        # 手数料
        commission = available * self.commission_rate

        return {
            'type': trade_type,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'size': size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'commission': commission
        }

    def _close_position(self, position, exit_price, exit_time, capital):
        """ポジション決済"""
        entry_price = position['entry_price']
        size = position['size']
        trade_type = position['type']

        # 損益計算
        if trade_type == 'BUY':
            pnl_before_commission = (exit_price - entry_price) * size
        else:  # SELL
            pnl_before_commission = (entry_price - exit_price) * size

        # 決済時の手数料
        exit_commission = exit_price * size * self.commission_rate

        # 純損益
        net_pnl = pnl_before_commission - position['commission'] - exit_commission

        # 資金更新
        exit_capital = capital + net_pnl

        return {
            'type': trade_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'entry_time': position['entry_time'],
            'exit_time': exit_time,
            'size': size,
            'pnl': net_pnl,
            'pnl_pct': (net_pnl / capital) * 100,
            'exit_capital': exit_capital,
            'hold_time': (exit_time - position['entry_time']).total_seconds() / 3600  # 時間
        }

    def _check_close_position(self, position, current_price, market_data, trading_logic):
        """ポジション決済判定"""
        entry_price = position['entry_price']
        trade_type = position['type']

        # ストップロス/テイクプロフィットチェック
        if trade_type == 'BUY':
            if current_price <= position['stop_loss']:
                logger.info(f"   Stop Loss Hit: {current_price:.2f} <= {position['stop_loss']:.2f}")
                return True
            if current_price >= position['take_profit']:
                logger.info(f"   Take Profit Hit: {current_price:.2f} >= {position['take_profit']:.2f}")
                return True

            # 反転シグナルチェック（SELL信号）
            should_trade, signal_type, _, confidence, _, _ = trading_logic.should_trade(market_data, None)
            if should_trade and signal_type == 'SELL' and confidence >= 1.8:
                logger.info(f"   Reversal Signal: SELL with confidence {confidence:.2f}")
                return True

        else:  # SELL
            if current_price >= position['stop_loss']:
                logger.info(f"   Stop Loss Hit: {current_price:.2f} >= {position['stop_loss']:.2f}")
                return True
            if current_price <= position['take_profit']:
                logger.info(f"   Take Profit Hit: {current_price:.2f} <= {position['take_profit']:.2f}")
                return True

            # 反転シグナルチェック（BUY信号）
            should_trade, signal_type, _, confidence, _, _ = trading_logic.should_trade(market_data, None)
            if should_trade and signal_type == 'BUY' and confidence >= 1.8:
                logger.info(f"   Reversal Signal: BUY with confidence {confidence:.2f}")
                return True

        return False

    def _calculate_performance(self, final_capital):
        """パフォーマンスメトリクス計算"""
        if not self.trades:
            return {
                'final_capital': final_capital,
                'total_return': 0,
                'total_return_pct': 0,
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0
            }

        # 基本統計
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] < 0]

        wins = len(winning_trades)
        losses = len(losing_trades)

        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))

        # プロフィットファクター
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # 最大ドローダウン
        equity_values = [e['equity'] for e in self.equity_curve]
        peak = equity_values[0]
        max_dd = 0

        for equity in equity_values:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # シャープレシオ（簡易版）
        returns = [t['pnl_pct'] for t in self.trades]
        avg_return = np.mean(returns) if returns else 0
        std_return = np.std(returns) if returns else 1
        sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0

        return {
            'final_capital': final_capital,
            'total_return': final_capital - self.initial_capital,
            'total_return_pct': ((final_capital - self.initial_capital) / self.initial_capital) * 100,
            'total_trades': total_trades,
            'winning_trades': wins,
            'losing_trades': losses,
            'win_rate': (wins / total_trades * 100) if total_trades > 0 else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe_ratio,
            'avg_trade_pnl': np.mean([t['pnl'] for t in self.trades]),
            'avg_win': np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0,
            'avg_loss': np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0,
            'avg_hold_time': np.mean([t['hold_time'] for t in self.trades])
        }

    def _print_performance(self, perf):
        """パフォーマンス結果表示"""
        print(f"\n{'='*60}")
        print(f"  BACKTEST RESULTS")
        print(f"{'='*60}")
        print(f"  Initial Capital:     ¥{self.initial_capital:>12,.0f}")
        print(f"  Final Capital:       ¥{perf['final_capital']:>12,.0f}")
        print(f"  Total Return:        ¥{perf['total_return']:>12,.2f} ({perf['total_return_pct']:>6.2f}%)")
        print(f"{'-'*60}")
        print(f"  Total Trades:        {perf['total_trades']:>12}")
        print(f"  Winning Trades:      {perf['winning_trades']:>12}")
        print(f"  Losing Trades:       {perf['losing_trades']:>12}")
        print(f"  Win Rate:            {perf['win_rate']:>11.2f}%")
        print(f"{'-'*60}")
        print(f"  Gross Profit:        ¥{perf['gross_profit']:>12,.2f}")
        print(f"  Gross Loss:          ¥{perf['gross_loss']:>12,.2f}")
        print(f"  Profit Factor:       {perf['profit_factor']:>12.2f}")
        print(f"{'-'*60}")
        print(f"  Avg Trade P/L:       ¥{perf['avg_trade_pnl']:>12,.2f}")
        print(f"  Avg Winning Trade:   ¥{perf['avg_win']:>12,.2f}")
        print(f"  Avg Losing Trade:    ¥{perf['avg_loss']:>12,.2f}")
        print(f"  Avg Hold Time:       {perf['avg_hold_time']:>11.2f} hours")
        print(f"{'-'*60}")
        print(f"  Max Drawdown:        {perf['max_drawdown']:>11.2f}%")
        print(f"  Sharpe Ratio:        {perf['sharpe_ratio']:>12.2f}")
        print(f"{'='*60}\n")

    def export_trades_csv(self, filename="backtest_trades.csv"):
        """取引履歴をCSV出力"""
        if not self.trades:
            logger.warning("No trades to export")
            return

        df = pd.DataFrame(self.trades)
        df.to_csv(filename, index=False)
        logger.info(f"Trades exported to {filename}")

    def plot_equity_curve(self):
        """エクイティカーブをプロット（オプション）"""
        try:
            import matplotlib.pyplot as plt

            df = pd.DataFrame(self.equity_curve)

            plt.figure(figsize=(12, 6))
            plt.plot(df['timestamp'], df['equity'], label='Equity', linewidth=2)
            plt.axhline(y=self.initial_capital, color='gray', linestyle='--', label='Initial Capital')
            plt.xlabel('Time')
            plt.ylabel('Equity (JPY)')
            plt.title('Equity Curve')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig('equity_curve.png')
            logger.info("Equity curve saved to equity_curve.png")

        except ImportError:
            logger.warning("matplotlib not installed - cannot plot equity curve")


if __name__ == "__main__":
    """バックテスト実行例"""
    import sys
    from config import load_config

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # 設定読み込み
    config = load_config()
    api_key = config.get('api_credentials', 'api_key')
    api_secret = config.get('api_credentials', 'api_secret')

    # データ取得
    data_service = DataService(api_key, api_secret)

    logger.info("Fetching historical data...")
    df = data_service.get_data_with_indicators(
        symbol='DOGE_JPY',
        interval='5m',
        limit=500,  # 過去500本（約41時間分）
        force_refresh=True
    )

    if df is None or df.empty:
        logger.error("Failed to get historical data")
        sys.exit(1)

    # バックテスト実行（2つの戦略を比較）
    print("\n" + "="*60)
    print("  STRATEGY COMPARISON: Enhanced vs Optimized")
    print("="*60 + "\n")

    # 1. 現在の戦略（Enhanced）
    print("Testing Strategy 1: Enhanced Trading Logic")
    enhanced_logic = EnhancedTradingLogic()
    backtest1 = BacktestEngine(initial_capital=10000)
    perf1 = backtest1.run_backtest(df, enhanced_logic)

    # 2. 最適化戦略（Optimized）
    print("\n" + "-"*60 + "\n")
    print("Testing Strategy 2: Optimized Trading Logic")
    optimized_logic = OptimizedTradingLogic()
    backtest2 = BacktestEngine(initial_capital=10000)
    perf2 = backtest2.run_backtest(df, optimized_logic)

    # 比較結果
    print("\n" + "="*60)
    print("  STRATEGY COMPARISON SUMMARY")
    print("="*60)
    print(f"{'Metric':<25} {'Enhanced':>15} {'Optimized':>15} {'Winner':>10}")
    print("-"*60)

    metrics = [
        ('Total Return %', 'total_return_pct'),
        ('Total Trades', 'total_trades'),
        ('Win Rate %', 'win_rate'),
        ('Profit Factor', 'profit_factor'),
        ('Max Drawdown %', 'max_drawdown'),
        ('Sharpe Ratio', 'sharpe_ratio')
    ]

    for label, key in metrics:
        val1 = perf1[key]
        val2 = perf2[key]

        # 勝者判定（最大DDは低い方が良い）
        if key == 'max_drawdown':
            winner = 'Enhanced' if val1 < val2 else 'Optimized'
        else:
            winner = 'Enhanced' if val1 > val2 else 'Optimized'

        print(f"{label:<25} {val1:>15.2f} {val2:>15.2f} {winner:>10}")

    print("="*60 + "\n")
