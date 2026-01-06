import pandas as pd
import logging
import sys
import random
from datetime import datetime, timedelta
from services.gmo_api import GMOCoinAPI
from services.technical_indicators import TechnicalIndicators

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class DataService:
    """
    Service for fetching and managing market data
    """
    
    def __init__(self, api_key=None, api_secret=None, db_session=None):
        """
        Initialize data service
        
        :param api_key: GMO Coin API key
        :param api_secret: GMO Coin API secret
        :param db_session: Database session for database operations
        """
        self.api = GMOCoinAPI(api_key, api_secret)
        self.db_session = db_session
        self.cache = {}
        self.cache_timeout = 60  # Cache timeout in seconds
    
    def _convert_interval_for_api(self, interval):
        """
        UI設定の時間足をGMO Coin API形式に変換

        :param interval: UI設定の間隔 (5m, 1h, etc.)
        :return: GMO API用の間隔 (5min, 1h, etc.)

        Note: GMO Coin APIがサポートしているのは: 1min, 5min, 15min, 30minのみ
              1h, 4h, 8h, 12h, 1dは非サポート（ERR-5207エラーになる）
        """
        # GMO Coin APIがサポートしている時間足のみ
        conversion_map = {
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '30m': '30min',
            '1min': '1min',
            '5min': '5min',
            '15min': '15min',
            '30min': '30min'
        }

        # サポートされていない時間足の警告と自動変換
        unsupported_intervals = {
            '1h': '30min',
            '4h': '30min',
            '8h': '30min',
            '12h': '30min',
            '1d': '30min',
            '1hour': '30min',
            '4hour': '30min',
            '1day': '30min'
        }

        if interval in unsupported_intervals:
            fallback = unsupported_intervals[interval]
            logger.warning(f"⚠️ GMO Coin API does NOT support '{interval}' timeframe!")
            logger.warning(f"⚠️ Automatically converting to '{fallback}' (maximum supported interval)")
            logger.warning(f"⚠️ Supported intervals: 1min, 5min, 15min, 30min ONLY")
            return fallback

        converted = conversion_map.get(interval, '30min')  # デフォルトは30min
        if converted != interval:
            logger.info(f"Converting interval: {interval} -> {converted}")
        return converted
    
    def get_ticker(self, symbol="DOGE_JPY"):
        """
        Get current ticker information
        
        :param symbol: Trading pair symbol
        :return: Ticker data
        """
        cache_key = f"ticker_{symbol}"
        
        # Check cache first
        if cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if datetime.now() - cache_time < timedelta(seconds=self.cache_timeout):
                return cache_data
        
        # Fetch fresh data
        response = self.api.get_ticker(symbol)
        logger.debug(f"Ticker response: {response}")

        if isinstance(response, dict):
            # レスポンスが {'data': [...]} 形式の場合
            if 'data' in response:
                data = response['data']
                # dataがリストの場合は最初の要素を取得
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                # Cache the result
                self.cache[cache_key] = (datetime.now(), data)
                return data
            # レスポンスが直接 {'ask': ..., 'bid': ..., 'last': ...} 形式の場合
            elif 'last' in response or 'ask' in response:
                # Cache the result
                self.cache[cache_key] = (datetime.now(), response)
                return response
            else:
                logger.warning(f"Unexpected ticker data format: {response}")
                return None
        else:
            logger.error(f"Failed to get ticker data: {response}")
            return None
    
    def get_klines(self, symbol="DOGE_JPY", interval="1h", limit=100, force_refresh=False):
        """
        Get candlestick/OHLCV data
        
        :param symbol: Trading pair symbol
        :param interval: Time interval (1min, 5min, 10min, 15min, 30min, 1h, 4h, 8h, 12h, 1d, 1w)
        :param limit: Number of candles to fetch
        :param force_refresh: 強制的にAPIから新しいデータを取得する
        :return: DataFrame with OHLCV data
        """
        # UI設定の時間足をGMO API形式に変換
        api_interval = self._convert_interval_for_api(interval)
        logger.info(f"Fetching klines data for {symbol}, interval: {interval} (API: {api_interval}), force_refresh: {force_refresh}")
        
        # 強制更新が指定されていない場合のみデータベースを確認
        if not force_refresh and hasattr(self, 'db_session') and self.db_session:
            try:
                from models import MarketData
                from sqlalchemy import desc
                logger.info(f"Attempting to get {limit} records for {symbol} from database first")
                
                # データベースからデータを取得
                market_data = self.db_session.query(MarketData).filter_by(
                    currency_pair=symbol
                ).order_by(
                    desc(MarketData.timestamp)
                ).limit(limit).all()
                
                if market_data and len(market_data) >= limit * 0.7:  # データベースに少なくとも70%のデータがある場合
                    logger.info(f"Found {len(market_data)} records in database, using cached data")
                    
                    # データポイントをリストに変換
                    data_points = []
                    for point in market_data:
                        data_points.append([
                            int(point.timestamp.timestamp() * 1000),  # Unix timestamp in ms
                            float(point.open_price),
                            float(point.high_price),
                            float(point.low_price),
                            float(point.close_price),
                            float(point.volume)
                        ])
                    
                    # 逆順にして時系列を正しく並べる
                    data_points.reverse()
                    df = self._convert_klines_to_dataframe(data_points)
                    if df is not None and not df.empty:
                        logger.info(f"Successfully loaded {len(df)} data points from database")
                        return df
            except Exception as db_e:
                logger.error(f"Error retrieving data from database: {db_e}")
                # データベース取得に失敗した場合はAPIでフォールバック
        
        # キャッシュをチェック
        cache_key = f"klines_{symbol}_{interval}_{limit}"
        if cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if datetime.now() - cache_time < timedelta(seconds=self.cache_timeout):
                logger.info(f"Using cached klines data for {symbol}, interval: {interval}")
                return cache_data
        
        # APIからデータを取得
        all_klines = []
        
        logger.info(f"Fetching klines data from API for {symbol}, interval: {api_interval}")
        
        # GMO Coin APIは過去の日付パラメータが必須
        logger.info(f"Attempting to get historical data with date parameter")
        
        # 最低限必要なデータポイント数
        min_required_datapoints = min(limit, 24)  # 少なくとも1日分のデータ
        # 過去に遡れる最大日数（1ヶ月）
        max_days_to_try = 30
        success = False
        response = None
        
        # 現在から過去に向かって日付を遡る
        for days_ago in range(1, max_days_to_try + 1):
            target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
            logger.info(f"Trying to fetch data for date: {target_date}")
            
            response = self.api.get_klines(symbol=symbol, interval=api_interval, date=target_date)
            
            if isinstance(response, dict) and 'data' in response and response['data']:
                logger.info(f"Successfully fetched {len(response['data'])} data points for date {target_date}")
                all_klines.extend(response['data'])
                success = True
                
                # 十分なデータが集まったかチェック
                if len(all_klines) >= min_required_datapoints:
                    break
            else:
                logger.warning(f"No data for date {target_date}: {response}")
        
        if not success or not all_klines:
            logger.warning("Failed to get sufficient klines data from API")
            # フォールバックデータ生成を試行
            logger.info("Primary data source failed, trying enhanced fallback")
            df = self._create_enhanced_fallback_data(symbol, interval, limit)
            if df is not None:
                return df
            
            logger.info(f"Enhanced fallback failed, trying database with resampling to {interval}")
            # データベースから異なる間隔のデータを取得してリサンプリングを試行
            if hasattr(self, 'db_session') and self.db_session:
                try:
                    from models import MarketData
                    from sqlalchemy import desc
                    
                    # より多くのデータを取得（最大500件）
                    market_data = self.db_session.query(MarketData).filter_by(
                        currency_pair=symbol
                    ).order_by(
                        desc(MarketData.timestamp)
                    ).limit(500).all()
                    
                    if market_data and len(market_data) > 10:
                        logger.info(f"Found {len(market_data)} historical records, attempting to create dataset")
                        
                        # データポイントをリストに変換
                        data_points = []
                        for point in market_data:
                            data_points.append([
                                int(point.timestamp.timestamp() * 1000),
                                float(point.open_price),
                                float(point.high_price),
                                float(point.low_price),
                                float(point.close_price),
                                float(point.volume)
                            ])
                        
                        # 逆順にして時系列を正しく並べる
                        data_points.reverse()
                        df = self._convert_klines_to_dataframe(data_points)
                        
                        if df is not None and not df.empty:
                            logger.info(f"Successfully created {len(df)} data points from database")
                            return df
                except Exception as db_e:
                    logger.error(f"Error with database fallback: {db_e}")
            
            logger.error("All data sources failed")
            return None
        
        # データを制限
        if len(all_klines) > limit:
            all_klines = all_klines[-limit:]
        
        logger.info(f"Processing {len(all_klines)} klines data points")
        
        # Convert to DataFrame
        df = self._convert_klines_to_dataframe(all_klines)
        
        if df is not None:
            # Cache the result
            self.cache[cache_key] = (datetime.now(), df)
            return df
        else:
            logger.error("Failed to convert klines data to DataFrame")
            return None
    
    def _convert_klines_to_dataframe(self, klines_data):
        """
        Convert klines data to DataFrame
        
        :param klines_data: List of klines data
        :return: DataFrame with OHLCV data
        """
        try:
            if not klines_data:
                logger.warning("No klines data provided")
                return None
            
            # Check if data is in dictionary format (new GMO API format)
            if isinstance(klines_data[0], dict):
                # Convert dictionary format to DataFrame
                df_data = []
                for item in klines_data:
                    df_data.append({
                        'timestamp': pd.to_datetime(int(item['openTime']), unit='ms'),
                        'open': float(item['open']),
                        'high': float(item['high']),
                        'low': float(item['low']),
                        'close': float(item['close']),
                        'volume': float(item['volume'])
                    })
                df = pd.DataFrame(df_data)
            else:
                # Old format - Create DataFrame from klines data
                df = pd.DataFrame(klines_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Convert data types
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove any invalid data
            df = df.dropna()
            
            if df.empty:
                logger.warning("No valid data after conversion")
                return None
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            logger.info(f"Converted {len(df)} klines data points to DataFrame")
            return df
            
        except Exception as e:
            logger.error(f"Error converting klines to DataFrame: {e}")
            logger.error(f"Sample data: {klines_data[:2] if klines_data else 'None'}")
            return None
    
    def _resample_to_4hour(self, df_30min):
        """
        30分足データを4時間足にリサンプリング

        :param df_30min: 30分足のDataFrame
        :return: 4時間足のDataFrame
        """
        try:
            if df_30min is None or df_30min.empty:
                logger.error("Empty dataframe for resampling")
                return None

            logger.info(f"🔄 Resampling 30min data to 4hour: {len(df_30min)} candles")

            # timestampをインデックスに設定
            df_resampled = df_30min.set_index('timestamp')

            # 4時間足にリサンプリング（30分 × 8 = 4時間）
            # - open: 最初の値
            # - high: 最大値
            # - low: 最小値
            # - close: 最後の値
            # - volume: 合計
            df_4h = df_resampled.resample('4H').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })

            # NaNを削除（不完全な足）
            df_4h = df_4h.dropna()

            # インデックスをリセット
            df_4h = df_4h.reset_index()

            logger.info(f"✅ Resampling complete: {len(df_30min)} → {len(df_4h)} candles (4hour)")
            logger.info(f"   4hour candles timerange: {df_4h['timestamp'].min()} to {df_4h['timestamp'].max()}")

            return df_4h

        except Exception as e:
            logger.error(f"Error resampling to 4hour: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_data_with_indicators(self, symbol="DOGE_JPY", interval="1h", limit=100, force_refresh=False):
        """
        Get market data with technical indicators

        :param symbol: Trading pair symbol
        :param interval: Time interval
        :param limit: Number of data points
        :param force_refresh: Force refresh from API
        :return: DataFrame with OHLCV data and technical indicators
        """
        logger.info(f"Getting data with indicators for {symbol}, interval={interval}, force_refresh={force_refresh}")

        # 4時間足が要求された場合、30分足から構築
        if interval in ['4hour', '4h', '4H']:
            logger.info("🎯 4hour timeframe requested - will resample from 30min data")

            # 4時間足 × limit本 = 30分足 × (limit × 8)本が必要
            # さらに、途中で切れることを考慮して余裕を持たせる
            min_30min_candles = limit * 8 * 2  # 2倍の余裕

            logger.info(f"📊 Fetching {min_30min_candles} × 30min candles for {limit} × 4hour candles")

            # 30分足データを取得
            df_30min = self.get_klines(symbol, '30min', min_30min_candles, force_refresh)

            if df_30min is None or df_30min.empty:
                logger.error("Failed to get 30min klines data for resampling")
                return None

            # 4時間足にリサンプリング
            df = self._resample_to_4hour(df_30min)

            if df is None or df.empty:
                logger.error("Failed to resample to 4hour")
                return None

            # 必要な本数に制限
            if len(df) > limit:
                df = df.tail(limit).reset_index(drop=True)
                logger.info(f"✂️ Trimmed to {limit} × 4hour candles")
        else:
            # Get raw klines data (通常の処理)
            df = self.get_klines(symbol, interval, limit, force_refresh)

        if df is None or df.empty:
            logger.error("Failed to get klines data")
            return None

        try:
            # Update the last candle with current ticker price if available
            logger.info("Updating last candle with current price")
            ticker_data = self.get_ticker(symbol)
            if ticker_data:
                # ticker_data is already a dict, not a list
                current_price = float(ticker_data.get('last', ticker_data.get('bid', 0)))
                if current_price > 0:
                    # Update the last row's close price to current price safely
                    try:
                        if 'close' in df.columns:
                            df.loc[df.index[-1], 'close'] = current_price
                            logger.info(f"Updated last candle close price to current: {current_price}")
                        else:
                            logger.warning("'close' column not found in DataFrame")
                    except Exception as e:
                        logger.error(f"Error updating close price: {e}")

            # Add technical indicators
            df_with_indicators = TechnicalIndicators.add_all_indicators(df)
            logger.info("All technical indicators added successfully")

            return df_with_indicators

        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return df
    
    def get_account_margin(self):
        """
        Get margin account information
        
        :return: Margin account data
        """
        try:
            return self.api.get_account_margin()
        except Exception as e:
            logger.error(f"Error getting margin account: {e}")
            return None
    
    def get_positions(self, symbol=None):
        """
        Get open positions
        
        :param symbol: Trading pair symbol (optional filter)
        :return: Positions data
        """
        try:
            return self.api.get_positions(symbol)
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return None
    
    def close_position(self, position_id, size=None):
        """
        Close a specific position
        
        :param position_id: Position ID to close
        :param size: Size to close (optional, closes all if not specified)
        :return: Close order result
        """
        try:
            return self.api.close_position(position_id, size)
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None
    
    def close_all_positions_by_symbol(self, symbol, side=None):
        """
        Close all positions for a symbol
        
        :param symbol: Trading pair symbol
        :param side: Position side to close (BUY/SELL), all if None
        :return: Close results
        """
        try:
            return self.api.close_all_positions_by_symbol(symbol, side)
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return False
    
    def _create_enhanced_fallback_data(self, symbol="DOGE_JPY", interval="1h", limit=100):
        """
        创建增强的回退数据，用于技术指标计算
        
        :param symbol: 交易对符号
        :param interval: 时间间隔
        :param limit: 数据点数量
        :return: 包含OHLCV数据的DataFrame
        """
        logger.info(f"Creating enhanced fallback data for {symbol}, interval={interval}, limit={limit}")
        
        try:
            # 获取当前价格
            ticker_data = self.get_ticker(symbol)
            if not ticker_data or not isinstance(ticker_data, list) or len(ticker_data) == 0:
                logger.error("Cannot get current ticker data for fallback generation")
                return None
                
            current_price = float(ticker_data[0]['last'])
            high_price = float(ticker_data[0].get('high', current_price * 1.02))
            low_price = float(ticker_data[0].get('low', current_price * 0.98))
            volume = float(ticker_data[0].get('volume', 1000000))
            
            logger.info(f"Base data - Price: {current_price}, High: {high_price}, Low: {low_price}, Volume: {volume}")
            
            # 生成时间间隔
            now = datetime.now()
            if interval in ['1min', '1m']:
                time_delta = timedelta(minutes=1)
            elif interval in ['5min', '5m']:
                time_delta = timedelta(minutes=5)
            elif interval in ['15min', '15m']:
                time_delta = timedelta(minutes=15)
            elif interval in ['30min', '30m']:
                time_delta = timedelta(minutes=30)
            elif interval in ['1h']:
                time_delta = timedelta(hours=1)
            elif interval in ['4h']:
                time_delta = timedelta(hours=4)
            elif interval in ['1d']:
                time_delta = timedelta(days=1)
            else:  # Default to 1h
                time_delta = timedelta(hours=1)
            
            # 创建更现实的价格数据
            df_data = []
            price_volatility = (high_price - low_price) / current_price
            price_volatility = max(0.01, min(0.05, price_volatility))  # 限制波动率在1%-5%之间
            
            # 生成趋势
            trend = random.choice(['bullish', 'bearish', 'neutral'])
            trend_strength = random.uniform(0.3, 0.8)
            
            logger.info(f"Generated trend: {trend} with strength: {trend_strength:.2f}")
            
            for i in range(limit):
                timestamp = now - time_delta * (limit - i - 1)
                
                # 计算基准价格（有趋势性）
                progress = i / limit  # 从0到1
                if trend == 'bullish':
                    base_price = low_price * (1 - progress) + current_price * progress
                elif trend == 'bearish':
                    base_price = high_price * (1 - progress) + current_price * progress
                else:  # neutral
                    base_price = current_price * (1 + random.uniform(-0.02, 0.02))
                
                # 添加随机噪音
                noise = random.uniform(-price_volatility, price_volatility) * (1 - progress * 0.5)
                adjusted_price = base_price * (1 + noise)
                
                # 生成OHLC数据
                candle_volatility = random.uniform(0.005, 0.02)  # 单个蜡烛的波动率
                open_price = adjusted_price * (1 + random.uniform(-candle_volatility/2, candle_volatility/2))
                close_price = adjusted_price * (1 + random.uniform(-candle_volatility/2, candle_volatility/2))
                
                high_candle = max(open_price, close_price) * random.uniform(1.001, 1 + candle_volatility)
                low_candle = min(open_price, close_price) * random.uniform(1 - candle_volatility, 0.999)
                
                # 确保最后一个数据点使用当前价格
                if i == limit - 1:
                    close_price = current_price
                    high_candle = max(high_candle, current_price)
                    low_candle = min(low_candle, current_price)
                
                # 生成相对现实的成交量（基于当天成交量）
                volume_variation = random.uniform(0.5, 1.5)
                adjusted_volume = volume * volume_variation * random.uniform(0.8, 1.2)
                
                df_data.append([
                    int(timestamp.timestamp() * 1000),  # timestamp
                    round(open_price, 3),               # open
                    round(high_candle, 3),              # high
                    round(low_candle, 3),               # low
                    round(close_price, 3),              # close
                    int(adjusted_volume)                # volume
                ])
            
            # 转换为DataFrame
            df = self._convert_klines_to_dataframe(df_data)
            
            if df is not None and not df.empty:
                logger.info(f"Enhanced fallback data created: {len(df)} records")
                # Cache the result
                cache_key = f"klines_{symbol}_{interval}_{limit}"
                self.cache[cache_key] = (datetime.now(), df)
                return df
            
        except Exception as e:
            logger.error(f"Error creating enhanced fallback data: {e}")
            
        return None
    
    def save_market_data_to_db(self, symbol, df):
        """
        Save market data to database for future use
        
        :param symbol: Trading pair symbol
        :param df: DataFrame with market data
        :return: Success status
        """
        if not hasattr(self, 'db_session') or not self.db_session:
            logger.warning("No database session available, cannot save market data")
            return False
        
        try:
            from models import MarketData
            
            # データベースに保存（既存データとの重複を避ける）
            saved_count = 0
            for _, row in df.iterrows():
                # 既存データをチェック
                existing = self.db_session.query(MarketData).filter_by(
                    currency_pair=symbol,
                    timestamp=row['timestamp']
                ).first()
                
                if not existing:
                    market_data = MarketData(
                        currency_pair=symbol,
                        timestamp=row['timestamp'],
                        open_price=row['open'],
                        high_price=row['high'],
                        low_price=row['low'],
                        close_price=row['close'],
                        volume=row['volume']
                    )
                    self.db_session.add(market_data)
                    saved_count += 1
            
            if saved_count > 0:
                self.db_session.commit()
                logger.info(f"Saved {saved_count} new market data points to database")
            else:
                logger.info("No new market data to save")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving market data to database: {e}")
            try:
                self.db_session.rollback()
            except:
                pass
            return False