"""
ローリング最適化エンジン v1.0
直近のローソク足データでパラメータ組み合わせをバックテストし、最適パラメータを自動選択

方針:
- 毎N分（デフォルト15分）に直近100本の15分足でシミュレーション
- SL, トレーリング閾値, MACDフィルターなどの組み合わせをテスト
- 純利益（手数料込み）が最大のパラメータセットを採用
- 追加コストゼロ（既存データ + CPU演算のみ）
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from itertools import product

logger = logging.getLogger(__name__)


class RollingOptimizer:
    """
    ローリングパラメータ最適化エンジン

    直近のローソク足データで各パラメータ組み合わせの成績をシミュレーションし、
    最も利益が出たパラメータセットを返す。
    """

    def __init__(self):
        self.last_optimization_time = None
        self.optimization_interval = 900  # 15分ごとに最適化
        self.current_best_params = None
        self.optimization_history = []  # 直近の最適化結果を保持

        # パラメータ探索空間
        # DOGE/JPYの15分足ではMACDヒストグラムが非常に小さい（0.001〜0.01程度）
        self.param_grid = {
            'stop_loss_pct': [0.006, 0.008, 0.010, 0.012, 0.015],
            'breakeven_threshold': [0.003, 0.005, 0.007],
            'entry_hist_filter': [0.001, 0.002, 0.003, 0.005],
            'close_hist_filter': [0.0005, 0.001, 0.002, 0.003],
            'macd_preset': ['standard', 'fast', 'slow'],
        }

        self.macd_presets = {
            'standard': {'fast': 12, 'slow': 26, 'signal': 9},
            'fast': {'fast': 8, 'slow': 17, 'signal': 9},
            'slow': {'fast': 15, 'slow': 30, 'signal': 9},
        }

        # トレーリングストップのテンプレート（breakeven_thresholdに基づいて動的生成）
        # 各段階: (含み益閾値, ロックするSL)
        self.trailing_templates = {
            0.003: [
                (0.003, 0.0), (0.006, 0.003), (0.010, 0.006), (0.015, 0.010), (0.025, 0.020),
            ],
            0.005: [
                (0.005, 0.0), (0.010, 0.005), (0.015, 0.010), (0.020, 0.015), (0.030, 0.020),
            ],
            0.007: [
                (0.007, 0.0), (0.012, 0.007), (0.017, 0.012), (0.022, 0.017), (0.035, 0.025),
            ],
        }

    def fetch_extended_data(self, data_service, symbol='DOGE_JPY', interval='15min', days=3):
        """
        最適化用に複数日のデータを取得（GMO APIは1日ずつしか返さないため）

        Args:
            data_service: DataServiceインスタンス
            symbol: 取引ペア
            interval: タイムフレーム
            days: 取得する日数（デフォルト3日 = 15分足で288本）

        Returns:
            DataFrame with indicators or None
        """
        try:
            from services.technical_indicators import TechnicalIndicators

            api_interval = data_service._convert_interval_for_api(interval)
            all_klines = []

            for days_ago in range(0, days):
                target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
                response = data_service.api.get_klines(symbol=symbol, interval=api_interval, date=target_date)

                if isinstance(response, dict) and 'data' in response and response['data']:
                    all_klines.extend(response['data'])

            if not all_klines:
                logger.warning("⚠️ No kline data fetched for optimization")
                return None

            # 重複除去（タイムスタンプで）して時系列ソート
            seen = set()
            unique_klines = []
            for k in all_klines:
                ts = k.get('openTime', k.get('timestamp', ''))
                if ts not in seen:
                    seen.add(ts)
                    unique_klines.append(k)

            df = data_service._convert_klines_to_dataframe(unique_klines)

            if df is None or df.empty:
                return None

            # 時系列ソート
            df = df.sort_index().reset_index(drop=True)

            # インジケーター追加
            df = TechnicalIndicators.add_all_indicators(df)

            logger.info(f"📊 [OPTIMIZER] Fetched {len(df)} candles ({days} days) for optimization")
            return df

        except Exception as e:
            logger.error(f"⚠️ Extended data fetch error: {e}")
            return None

    def should_optimize(self):
        """最適化を実行すべきか判定"""
        if self.last_optimization_time is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_optimization_time).total_seconds()
        return elapsed >= self.optimization_interval

    def optimize(self, df):
        """
        直近データでパラメータ最適化を実行

        Args:
            df: 15分足のDataFrame（100本以上推奨）

        Returns:
            dict: 最適パラメータ or None（データ不足時）
        """
        if df is None or len(df) < 50:
            logger.warning("⚠️ Insufficient data for optimization (need 50+ candles)")
            return self.current_best_params

        logger.info("🧠 === Rolling Optimization Start ===")
        start_time = datetime.now()

        best_params = None
        best_pnl = float('-inf')
        best_stats = None
        results = []

        # パラメータグリッド生成
        grid_keys = list(self.param_grid.keys())
        grid_values = list(self.param_grid.values())

        total_combos = 1
        for v in grid_values:
            total_combos *= len(v)
        logger.info(f"   Testing {total_combos} parameter combinations...")

        for combo in product(*grid_values):
            params = dict(zip(grid_keys, combo))

            # MACDプリセットを展開
            macd = self.macd_presets[params['macd_preset']]
            params['macd_fast'] = macd['fast']
            params['macd_slow'] = macd['slow']
            params['macd_signal'] = macd['signal']

            # トレーリングテンプレートを設定
            params['trailing_stops'] = self.trailing_templates[params['breakeven_threshold']]

            # シミュレーション実行
            stats = self._simulate_trades(df.copy(), params)

            if stats is not None:
                results.append((params.copy(), stats))
                # 最適パラメータ選択: 純利益 > 勝率 > 取引回数の少なさ（手数料削減）
                score = stats['net_pnl']
                if stats['total_trades'] > 0:
                    # 勝率ボーナス（50%以上で加算）
                    win_rate = stats['wins'] / stats['total_trades']
                    if win_rate > 0.5:
                        score += stats['net_pnl'] * 0.2  # 高勝率に20%ボーナス

                if score > best_pnl:
                    best_pnl = score
                    best_params = params.copy()
                    best_stats = stats

        elapsed = (datetime.now() - start_time).total_seconds()
        self.last_optimization_time = datetime.now(timezone.utc)

        if best_params and best_stats:
            self.current_best_params = best_params

            # 履歴に保存（最大10件）
            self.optimization_history.append({
                'time': datetime.now(timezone.utc).isoformat(),
                'params': best_params,
                'stats': best_stats,
            })
            if len(self.optimization_history) > 10:
                self.optimization_history.pop(0)

            logger.info(f"🧠 === Optimization Complete ({elapsed:.1f}s) ===")
            logger.info(f"   Best params:")
            logger.info(f"     SL: {best_params['stop_loss_pct']*100:.1f}%")
            logger.info(f"     Breakeven: +{best_params['breakeven_threshold']*100:.1f}%")
            logger.info(f"     Entry hist filter: {best_params['entry_hist_filter']:.3f}")
            logger.info(f"     Close hist filter: {best_params['close_hist_filter']:.3f}")
            logger.info(f"     MACD: {best_params['macd_preset']} ({best_params['macd_fast']}/{best_params['macd_slow']}/{best_params['macd_signal']})")
            logger.info(f"   Performance (backtest):")
            logger.info(f"     Net P&L: ¥{best_stats['net_pnl']:.1f}")
            logger.info(f"     Trades: {best_stats['total_trades']} (W:{best_stats['wins']} L:{best_stats['losses']})")
            if best_stats['total_trades'] > 0:
                wr = best_stats['wins'] / best_stats['total_trades'] * 100
                logger.info(f"     Win rate: {wr:.0f}%")
                logger.info(f"     Avg win: ¥{best_stats['avg_win']:.1f}, Avg loss: ¥{best_stats['avg_loss']:.1f}")

            # ログファイルにも記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"OPTIMIZATION: SL={best_params['stop_loss_pct']*100:.1f}% "
                            f"BE={best_params['breakeven_threshold']*100:.1f}% "
                            f"MACD={best_params['macd_preset']} "
                            f"PnL=¥{best_stats['net_pnl']:.1f} "
                            f"Trades={best_stats['total_trades']} "
                            f"WR={best_stats['wins']}/{best_stats['total_trades']}\n")
            except:
                pass
        else:
            logger.info(f"🧠 Optimization: no profitable parameters found, keeping current")

        return self.current_best_params

    def _simulate_trades(self, df, params):
        """
        パラメータセットでの取引をシミュレーション

        MACDクロスベースのエントリー/クローズをシミュレートし、
        トレーリングストップ、ハードSL、MACDクロス決済を含む完全な
        取引サイクルを再現する。

        Returns:
            dict: 取引統計 or None
        """
        try:
            closes = df['close'].values
            highs = df['high'].values
            lows = df['low'].values

            # MACDを指定パラメータで計算
            close_series = pd.Series(closes)
            ema_fast = close_series.ewm(span=params['macd_fast'], adjust=False).mean()
            ema_slow = close_series.ewm(span=params['macd_slow'], adjust=False).mean()
            macd_line = (ema_fast - ema_slow).values
            signal_line = pd.Series(macd_line).ewm(span=params['macd_signal'], adjust=False).mean().values
            histogram = macd_line - signal_line

            stop_loss_pct = params['stop_loss_pct']
            entry_hist_filter = params['entry_hist_filter']
            close_hist_filter = params['close_hist_filter']
            trailing_stops = params['trailing_stops']

            # シミュレーション状態
            position = None  # {'side': 'BUY'/'SELL', 'entry_price': float, 'size': 50}
            last_macd_pos = None
            trades = []
            fee_per_trade = 1.0  # ¥1/取引

            # 最低30本のウォームアップ（MACD安定化）
            start_idx = max(params['macd_slow'] + params['macd_signal'], 30)

            for i in range(start_idx, len(closes)):
                price = closes[i]
                high = highs[i]
                low = lows[i]
                ml = macd_line[i]
                ms = signal_line[i]
                hist = abs(ml - ms)

                # 確定済みローソク足のMACD位置（1本前）
                if i < 2:
                    continue
                confirmed_ml = macd_line[i - 1]
                confirmed_ms = signal_line[i - 1]
                confirmed_pos = 'above' if confirmed_ml > confirmed_ms else 'below'
                confirmed_hist = abs(confirmed_ml - confirmed_ms)

                prev_ml = macd_line[i - 2]
                prev_ms = signal_line[i - 2]
                prev_pos = 'above' if prev_ml > prev_ms else 'below'

                # MACDクロス検出（確定済みベース）
                is_golden = (prev_pos == 'below' and confirmed_pos == 'above')
                is_death = (prev_pos == 'above' and confirmed_pos == 'below')

                # === ポジション保有中: 決済判定 ===
                if position is not None:
                    side = position['side']
                    entry = position['entry_price']
                    size = position['size']

                    if side == 'BUY':
                        pl_ratio = (price - entry) / entry
                        # ローソク足内の最安値でSLチェック
                        worst_pl = (low - entry) / entry
                    else:
                        pl_ratio = (entry - price) / entry
                        worst_pl = (entry - high) / entry

                    # トレーリングストップ更新
                    peak_pl = position.get('peak_pl', 0.0)
                    if pl_ratio > peak_pl:
                        position['peak_pl'] = pl_ratio
                        peak_pl = pl_ratio

                    current_sl = -stop_loss_pct  # デフォルトはハードSL
                    for threshold, lock in trailing_stops:
                        if peak_pl >= threshold:
                            current_sl = lock

                    # SLチェック（ローソク足内の最悪値で判定）
                    if worst_pl <= current_sl:
                        # 実際の決済価格をSLレベルで推定
                        if current_sl >= 0:
                            exit_price = entry * (1 + current_sl) if side == 'BUY' else entry * (1 - current_sl)
                        else:
                            exit_price = entry * (1 + current_sl) if side == 'BUY' else entry * (1 - current_sl)

                        pnl = (exit_price - entry) * size if side == 'BUY' else (entry - exit_price) * size
                        trades.append({
                            'pnl': pnl,
                            'fees': fee_per_trade * 2,  # エントリー+決済
                            'reason': 'trailing_stop' if current_sl >= 0 else 'hard_sl',
                        })
                        position = None
                        continue

                    # MACDクロス決済
                    if side == 'BUY' and is_death and confirmed_hist > close_hist_filter:
                        pnl = (price - entry) * size
                        trades.append({
                            'pnl': pnl,
                            'fees': fee_per_trade * 2,
                            'reason': 'macd_cross',
                        })
                        position = None
                        # フォールスルーして反対エントリー判定へ

                    elif side == 'SELL' and is_golden and confirmed_hist > close_hist_filter:
                        pnl = (entry - price) * size
                        trades.append({
                            'pnl': pnl,
                            'fees': fee_per_trade * 2,
                            'reason': 'macd_cross',
                        })
                        position = None
                        # フォールスルーして反対エントリー判定へ

                # === ポジションなし: エントリー判定 ===
                if position is None:
                    if is_golden and confirmed_hist > entry_hist_filter:
                        position = {
                            'side': 'BUY',
                            'entry_price': price,
                            'size': 50,  # 固定サイズ（手数料比較のため統一）
                            'peak_pl': 0.0,
                        }
                    elif is_death and confirmed_hist > entry_hist_filter:
                        position = {
                            'side': 'SELL',
                            'entry_price': price,
                            'size': 50,
                            'peak_pl': 0.0,
                        }

            # 未決済ポジションは含み損益を計算（ただし統計には含めない）
            # 確定した取引のみで評価

            if len(trades) == 0:
                return {
                    'net_pnl': 0,
                    'gross_pnl': 0,
                    'total_fees': 0,
                    'total_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'avg_win': 0,
                    'avg_loss': 0,
                }

            # 統計計算
            gross_pnl = sum(t['pnl'] for t in trades)
            total_fees = sum(t['fees'] for t in trades)
            net_pnl = gross_pnl - total_fees

            wins = [t for t in trades if t['pnl'] > 0]
            losses = [t for t in trades if t['pnl'] <= 0]

            return {
                'net_pnl': net_pnl,
                'gross_pnl': gross_pnl,
                'total_fees': total_fees,
                'total_trades': len(trades),
                'wins': len(wins),
                'losses': len(losses),
                'avg_win': np.mean([t['pnl'] for t in wins]) if wins else 0,
                'avg_loss': np.mean([t['pnl'] for t in losses]) if losses else 0,
            }

        except Exception as e:
            logger.error(f"Simulation error: {e}")
            return None

    def get_status(self):
        """最適化ステータスを返す（ダッシュボード用）"""
        if self.current_best_params is None:
            return {'status': 'not_initialized', 'params': None}

        params = self.current_best_params
        last_history = self.optimization_history[-1] if self.optimization_history else None

        return {
            'status': 'active',
            'params': {
                'stop_loss_pct': params['stop_loss_pct'],
                'breakeven_threshold': params['breakeven_threshold'],
                'entry_hist_filter': params['entry_hist_filter'],
                'close_hist_filter': params['close_hist_filter'],
                'macd_preset': params['macd_preset'],
                'macd_fast': params['macd_fast'],
                'macd_slow': params['macd_slow'],
                'macd_signal': params['macd_signal'],
            },
            'last_optimization': last_history['time'] if last_history else None,
            'last_backtest_pnl': last_history['stats']['net_pnl'] if last_history else None,
            'last_backtest_trades': last_history['stats']['total_trades'] if last_history else None,
        }
