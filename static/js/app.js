/**
 * GMO Coin Trading Bot - アプリケーションJavaScript
 */

// グローバル変数
let priceChart = null;
let indicatorChart = null;
let currentSymbol = 'XRP_JPY';  // デフォルト通貨ペア
let currentInterval = '5min';   // デフォルト間隔（1分足を除外）
let currentIndicator = 'rsi';
let tradeConfirmModal = null;
let closeTradeModal = null;
let loadingChartData = false;

/**
 * アプリケーションの初期化
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log("アプリケーション初期化中...");

    // Bootstrapモーダルの初期化
    initModals();
    
    // イベントリスナーを設定
    setupEventListeners();
    
    // チャートデータを読み込み
    loadChartData(currentSymbol, currentInterval);
    
    // 取引統計を読み込み
    loadTradeStats();
    
    // 1分ごとにティッカー情報を更新
    setInterval(updateTickerInfo, 60000);
    
    // 自動更新（5分ごと）
    setInterval(() => {
        loadChartData(currentSymbol, currentInterval);
        loadTradeStats();
    }, 300000);
});

/**
 * Bootstrapモーダルの初期化
 */
function initModals() {
    const tradeConfirmModalElement = document.getElementById('tradeConfirmModal');
    if (tradeConfirmModalElement) {
        tradeConfirmModal = new bootstrap.Modal(tradeConfirmModalElement);
    }
    
    const closeTradeModalElement = document.getElementById('closeTradeModal');
    if (closeTradeModalElement) {
        closeTradeModal = new bootstrap.Modal(closeTradeModalElement);
    }
}

/**
 * イベントリスナーの設定
 */
function setupEventListeners() {
    // 間隔切り替えボタン
    document.querySelectorAll('.interval-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const interval = this.getAttribute('data-interval');
            if (interval !== currentInterval) {
                document.querySelectorAll('.interval-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentInterval = interval;
                loadChartData(currentSymbol, currentInterval);
            }
        });
    });
    
    // インジケーター切り替えボタン
    document.querySelectorAll('.indicator-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const indicator = this.getAttribute('data-indicator');
            if (indicator !== currentIndicator) {
                document.querySelectorAll('.indicator-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentIndicator = indicator;
                
                // 既存のデータでインジケーターを再描画
                if (window.chartData) {
                    renderIndicatorChart(window.chartData, currentIndicator);
                }
            }
        });
    });
    
    // 取引ペアの選択
    const symbolSelect = document.getElementById('trading-pair');
    if (symbolSelect) {
        symbolSelect.addEventListener('change', function() {
            currentSymbol = this.value;
            loadChartData(currentSymbol, currentInterval);
        });
    }
    
    // 買い/売りボタン
    const buyBtn = document.getElementById('buy-btn');
    const sellBtn = document.getElementById('sell-btn');
    
    if (buyBtn) {
        buyBtn.addEventListener('click', function() {
            prepareTradeConfirmation('buy');
        });
    }
    
    if (sellBtn) {
        sellBtn.addEventListener('click', function() {
            prepareTradeConfirmation('sell');
        });
    }
    
    // 取引確認ボタン
    const confirmTradeBtn = document.getElementById('confirm-trade-btn');
    if (confirmTradeBtn) {
        confirmTradeBtn.addEventListener('click', executeTrade);
    }
    
    // トレードを閉じるボタン
    document.addEventListener('click', function(e) {
        if (e.target && e.target.closest('.close-trade-btn')) {
            const tradeId = e.target.closest('.close-trade-btn').getAttribute('data-trade-id');
            document.getElementById('confirm-close-btn').setAttribute('data-trade-id', tradeId);
        }
    });
    
    // トレードを閉じる確認ボタン
    const confirmCloseBtn = document.getElementById('confirm-close-btn');
    if (confirmCloseBtn) {
        confirmCloseBtn.addEventListener('click', function() {
            const tradeId = this.getAttribute('data-trade-id');
            closeTrade(tradeId);
        });
    }
}

/**
 * チャートデータを読み込む
 */
function loadChartData(symbol, interval) {
    if (loadingChartData) return;
    
    loadingChartData = true;
    showLoading('チャートデータを読み込み中...');
    
    fetch(`/api/dashboard/chart-data?symbol=${symbol}&interval=${interval}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`サーバーエラー: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            hideLoading();
            loadingChartData = false;
            
            if (data.error) {
                showError(`データエラー: ${data.error}`);
                return;
            }
            
            // データを検証
            if (!data || !data.timestamps || !data.prices || data.timestamps.length === 0) {
                showError('チャートデータが無効です');
                return;
            }
            
            // データを安全に変換
            const cleanData = cleanChartData(data);
            
            // グローバル変数に保存（他の関数でアクセスできるように）
            window.chartData = cleanData;
            
            // チャートを描画
            renderPriceChart(cleanData);
            renderIndicatorChart(cleanData, currentIndicator);
            
            console.log('チャートを正常に描画しました');
        })
        .catch(error => {
            hideLoading();
            loadingChartData = false;
            showError(`データ取得エラー: ${error.message}`);
            console.error('チャートデータの取得エラー:', error);
        });
}

/**
 * チャートデータをクリーンアップする
 */
function cleanChartData(data) {
    try {
        // データが存在するか確認
        if (!data.timestamps || !data.prices || !data.prices.close) {
            throw new Error('無効なデータ構造');
        }
        
        // 有効なインデックスを収集
        const validIndices = [];
        for (let i = 0; i < data.timestamps.length; i++) {
            if (data.timestamps[i] && 
                data.prices.open[i] !== null && 
                data.prices.high[i] !== null && 
                data.prices.low[i] !== null && 
                data.prices.close[i] !== null) {
                validIndices.push(i);
            }
        }
        
        // 有効なデータのみを使用
        const cleanData = {
            timestamps: validIndices.map(i => data.timestamps[i]),
            prices: {
                open: validIndices.map(i => data.prices.open[i]),
                high: validIndices.map(i => data.prices.high[i]),
                low: validIndices.map(i => data.prices.low[i]),
                close: validIndices.map(i => data.prices.close[i])
            },
            volume: validIndices.map(i => data.volume[i]),
            indicators: {}
        };
        
        // インジケーターデータをコピー（存在する場合）
        if (data.indicators) {
            // SMA
            if (data.indicators.sma) {
                cleanData.indicators.sma = {
                    sma_20: validIndices.map(i => data.indicators.sma.sma_20 ? data.indicators.sma.sma_20[i] : null),
                    sma_50: validIndices.map(i => data.indicators.sma.sma_50 ? data.indicators.sma.sma_50[i] : null)
                };
            }
            
            // RSI
            if (data.indicators.rsi) {
                cleanData.indicators.rsi = validIndices.map(i => data.indicators.rsi[i]);
            }
            
            // MACD
            if (data.indicators.macd) {
                cleanData.indicators.macd = {
                    line: validIndices.map(i => data.indicators.macd.line ? data.indicators.macd.line[i] : null),
                    signal: validIndices.map(i => data.indicators.macd.signal ? data.indicators.macd.signal[i] : null),
                    histogram: validIndices.map(i => data.indicators.macd.histogram ? data.indicators.macd.histogram[i] : null)
                };
            }
            
            // Bollinger Bands
            if (data.indicators.bollinger) {
                cleanData.indicators.bollinger = {
                    upper: validIndices.map(i => data.indicators.bollinger.upper ? data.indicators.bollinger.upper[i] : null),
                    middle: validIndices.map(i => data.indicators.bollinger.middle ? data.indicators.bollinger.middle[i] : null),
                    lower: validIndices.map(i => data.indicators.bollinger.lower ? data.indicators.bollinger.lower[i] : null)
                };
            }
        }
        
        // トレードデータをコピー
        if (data.trades) {
            cleanData.trades = data.trades;
        }
        
        return cleanData;
    } catch (error) {
        console.error('データのクリーンアップエラー:', error);
        return data; // エラーが発生した場合は元のデータを返す
    }
}

/**
 * 価格チャートを描画する
 */
function renderPriceChart(data) {
    try {
        const ctx = document.getElementById('priceChart').getContext('2d');
        
        // 既存のチャートを破棄
        if (priceChart) {
            priceChart.destroy();
        }
        
        // データポイントを準備
        const chartData = [];
        const sma20Data = [];
        const sma50Data = [];
        
        for (let i = 0; i < data.timestamps.length; i++) {
            const date = new Date(data.timestamps[i]);
            
            // メインチャートのデータ
            chartData.push({
                x: date,
                y: parseFloat(data.prices.close[i])
            });
            
            // SMA データ（存在する場合）
            if (data.indicators && data.indicators.sma) {
                if (data.indicators.sma.sma_20 && data.indicators.sma.sma_20[i] !== null) {
                    sma20Data.push({
                        x: date,
                        y: parseFloat(data.indicators.sma.sma_20[i])
                    });
                }
                
                if (data.indicators.sma.sma_50 && data.indicators.sma.sma_50[i] !== null) {
                    sma50Data.push({
                        x: date,
                        y: parseFloat(data.indicators.sma.sma_50[i])
                    });
                }
            }
        }
        
        // 取引マーカーを追加
        const buyMarkers = [];
        const sellMarkers = [];
        
        if (data.trades && data.trades.length > 0) {
            data.trades.forEach(trade => {
                if (!trade || !trade.timestamp) return;
                
                const tradeDate = new Date(trade.timestamp);
                const price = parseFloat(trade.price);
                
                if (trade.trade_type === 'buy') {
                    buyMarkers.push({
                        x: tradeDate,
                        y: price * 0.998,
                        tradeId: trade.id
                    });
                } else if (trade.trade_type === 'sell') {
                    sellMarkers.push({
                        x: tradeDate,
                        y: price * 1.002,
                        tradeId: trade.id
                    });
                }
            });
        }
        
        // チャートデータセット
        const datasets = [
            {
                label: '価格',
                data: chartData,
                borderColor: 'rgba(56, 128, 255, 1)',
                backgroundColor: 'rgba(56, 128, 255, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.2,
                pointRadius: 0,
                pointHoverRadius: 3
            }
        ];
        
        // SMAを追加
        if (sma20Data.length > 0) {
            datasets.push({
                label: 'SMA 20',
                data: sma20Data,
                borderColor: 'rgba(255, 159, 64, 1)',
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false
            });
        }
        
        if (sma50Data.length > 0) {
            datasets.push({
                label: 'SMA 50',
                data: sma50Data,
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false
            });
        }
        
        // 取引マーカーを追加
        if (buyMarkers.length > 0) {
            datasets.push({
                label: '買い注文',
                data: buyMarkers,
                backgroundColor: 'rgba(75, 192, 192, 1)',
                pointStyle: 'triangle',
                pointRadius: 8,
                pointHoverRadius: 12
            });
        }
        
        if (sellMarkers.length > 0) {
            datasets.push({
                label: '売り注文',
                data: sellMarkers,
                backgroundColor: 'rgba(255, 99, 132, 1)',
                pointStyle: 'triangle',
                rotation: 180,
                pointRadius: 8,
                pointHoverRadius: 12
            });
        }
        
        // チャート作成
        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'auto',
                            displayFormats: {
                                minute: 'HH:mm',
                                hour: 'MM/dd HH:mm',
                                day: 'MM/dd',
                                week: 'yyyy/MM/dd',
                                month: 'yyyy/MM'
                            }
                        },
                        ticks: {
                            maxRotation: 0,
                            autoSkip: true,
                            color: 'rgba(255, 255, 255, 0.8)'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    },
                    y: {
                        position: 'right',
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString() + '¥';
                            },
                            color: 'rgba(255, 255, 255, 0.8)'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: 'rgba(255, 255, 255, 0.8)',
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y;
                                
                                if (label === '買い注文' || label === '売り注文') {
                                    return `${label} (ID: ${context.raw.tradeId})`;
                                }
                                
                                return `${label}: ${value.toLocaleString()}¥`;
                            },
                            title: function(tooltipItems) {
                                return new Date(tooltipItems[0].parsed.x).toLocaleString();
                            }
                        }
                    }
                }
            }
        });
        
        // トレードマーカークリックイベント
        document.getElementById('priceChart').onclick = function(evt) {
            const points = priceChart.getElementsAtEventForMode(evt, 'nearest', { intersect: true }, true);
            
            if (points.length) {
                const firstPoint = points[0];
                const dataset = priceChart.data.datasets[firstPoint.datasetIndex];
                
                if (dataset.label === '買い注文' || dataset.label === '売り注文') {
                    const tradeId = dataset.data[firstPoint.index].tradeId;
                    if (tradeId) {
                        window.location.href = `/dashboard/trade/${tradeId}`;
                    }
                }
            }
        };
        
    } catch (error) {
        console.error('価格チャートの描画エラー:', error);
        showError('チャートの描画に失敗しました');
    }
}

/**
 * インジケーターチャートを描画する
 */
function renderIndicatorChart(data, indicator) {
    try {
        const ctx = document.getElementById('indicatorChart').getContext('2d');
        
        // 既存のチャートを破棄
        if (indicatorChart) {
            indicatorChart.destroy();
        }
        
        // 共通オプション
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'auto',
                        displayFormats: {
                            minute: 'HH:mm',
                            hour: 'MM/dd HH:mm',
                            day: 'MM/dd',
                            week: 'yyyy/MM/dd',
                            month: 'yyyy/MM'
                        }
                    },
                    ticks: {
                        maxRotation: 0,
                        autoSkip: true,
                        color: 'rgba(255, 255, 255, 0.8)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.8)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: 'rgba(255, 255, 255, 0.8)',
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        };
        
        // インジケータータイプに基づいてチャートを作成
        if (indicator === 'rsi' && data.indicators && data.indicators.rsi) {
            // RSIチャート
            options.scales.y = {
                ...options.scales.y,
                min: 0,
                max: 100,
                grid: {
                    color: (context) => {
                        if (context.tick.value === 30 || context.tick.value === 70) {
                            return 'rgba(255, 99, 132, 0.5)';
                        }
                        return 'rgba(255, 255, 255, 0.1)';
                    }
                }
            };
            
            const rsiData = [];
            for (let i = 0; i < data.timestamps.length; i++) {
                if (data.indicators.rsi[i] !== null && data.indicators.rsi[i] !== undefined) {
                    rsiData.push({
                        x: new Date(data.timestamps[i]),
                        y: parseFloat(data.indicators.rsi[i])
                    });
                }
            }
            
            indicatorChart = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'RSI (14)',
                            data: rsiData,
                            borderColor: 'rgba(153, 102, 255, 1)',
                            backgroundColor: 'rgba(153, 102, 255, 0.2)',
                            borderWidth: 2,
                            fill: false
                        }
                    ]
                },
                options: options
            });
            
        } else if (indicator === 'macd' && data.indicators && data.indicators.macd) {
            // MACDチャート
            const macdLineData = [];
            const macdSignalData = [];
            const macdHistogramData = [];
            
            for (let i = 0; i < data.timestamps.length; i++) {
                const date = new Date(data.timestamps[i]);
                
                if (data.indicators.macd.line && data.indicators.macd.line[i] !== null) {
                    macdLineData.push({
                        x: date,
                        y: parseFloat(data.indicators.macd.line[i])
                    });
                }
                
                if (data.indicators.macd.signal && data.indicators.macd.signal[i] !== null) {
                    macdSignalData.push({
                        x: date,
                        y: parseFloat(data.indicators.macd.signal[i])
                    });
                }
                
                if (data.indicators.macd.histogram && data.indicators.macd.histogram[i] !== null) {
                    macdHistogramData.push({
                        x: date,
                        y: parseFloat(data.indicators.macd.histogram[i])
                    });
                }
            }
            
            indicatorChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    datasets: [
                        {
                            label: 'MACDヒストグラム',
                            data: macdHistogramData,
                            backgroundColor: (context) => {
                                const value = context.raw.y;
                                return value >= 0 ? 'rgba(75, 192, 192, 0.5)' : 'rgba(255, 99, 132, 0.5)';
                            },
                            borderColor: (context) => {
                                const value = context.raw.y;
                                return value >= 0 ? 'rgba(75, 192, 192, 1)' : 'rgba(255, 99, 132, 1)';
                            },
                            borderWidth: 1,
                            type: 'bar'
                        },
                        {
                            label: 'MACDライン',
                            data: macdLineData,
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 2,
                            pointRadius: 0,
                            type: 'line',
                            fill: false
                        },
                        {
                            label: 'シグナルライン',
                            data: macdSignalData,
                            borderColor: 'rgba(255, 159, 64, 1)',
                            borderWidth: 2,
                            pointRadius: 0,
                            type: 'line',
                            fill: false
                        }
                    ]
                },
                options: options
            });
            
        } else if (indicator === 'bollinger' && data.indicators && data.indicators.bollinger) {
            // ボリンジャーバンドチャート
            const priceData = [];
            const upperData = [];
            const middleData = [];
            const lowerData = [];
            
            for (let i = 0; i < data.timestamps.length; i++) {
                const date = new Date(data.timestamps[i]);
                
                priceData.push({
                    x: date,
                    y: parseFloat(data.prices.close[i])
                });
                
                if (data.indicators.bollinger.upper && data.indicators.bollinger.upper[i] !== null) {
                    upperData.push({
                        x: date,
                        y: parseFloat(data.indicators.bollinger.upper[i])
                    });
                }
                
                if (data.indicators.bollinger.middle && data.indicators.bollinger.middle[i] !== null) {
                    middleData.push({
                        x: date,
                        y: parseFloat(data.indicators.bollinger.middle[i])
                    });
                }
                
                if (data.indicators.bollinger.lower && data.indicators.bollinger.lower[i] !== null) {
                    lowerData.push({
                        x: date,
                        y: parseFloat(data.indicators.bollinger.lower[i])
                    });
                }
            }
            
            indicatorChart = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: '価格',
                            data: priceData,
                            borderColor: 'rgba(56, 128, 255, 1)',
                            borderWidth: 2,
                            pointRadius: 0,
                            fill: false
                        },
                        {
                            label: 'ミドルバンド',
                            data: middleData,
                            borderColor: 'rgba(255, 255, 255, 0.7)',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: false
                        },
                        {
                            label: 'アッパーバンド',
                            data: upperData,
                            borderColor: 'rgba(75, 192, 192, 0.7)',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            fill: false
                        },
                        {
                            label: 'ロワーバンド',
                            data: lowerData,
                            borderColor: 'rgba(255, 99, 132, 0.7)',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            fill: {
                                target: 2,
                                above: 'rgba(75, 192, 192, 0.1)',
                                below: 'rgba(255, 99, 132, 0.1)'
                            }
                        }
                    ]
                },
                options: options
            });
            
        } else if (indicator === 'volume') {
            // ボリュームチャート
            const volumeData = [];
            
            for (let i = 0; i < data.timestamps.length; i++) {
                if (data.volume[i] !== null && data.volume[i] !== undefined) {
                    volumeData.push({
                        x: new Date(data.timestamps[i]),
                        y: parseFloat(data.volume[i])
                    });
                }
            }
            
            indicatorChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    datasets: [
                        {
                            label: '取引量',
                            data: volumeData,
                            backgroundColor: 'rgba(54, 162, 235, 0.6)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    ...options,
                    scales: {
                        ...options.scales,
                        y: {
                            ...options.scales.y,
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return value.toLocaleString();
                                },
                                color: 'rgba(255, 255, 255, 0.8)'
                            }
                        }
                    }
                }
            });
        } else {
            // インジケーターデータが見つからない場合
            showError(`${indicator} データが見つかりません`);
            return;
        }
    } catch (error) {
        console.error('インジケーターチャートの描画エラー:', error);
        showError('インジケーターチャートの描画に失敗しました');
    }
}

/**
 * 取引統計を読み込む
 */
function loadTradeStats() {
    fetch('/api/dashboard/trade-stats')
        .then(response => response.json())
        .then(data => {
            updateTradeStats(data);
        })
        .catch(error => {
            console.error('取引統計の取得エラー:', error);
        });
}

/**
 * 取引統計を更新する
 */
function updateTradeStats(data) {
    // 残高の更新
    const balanceElement = document.getElementById('current-balance');
    if (balanceElement && data.balance !== undefined) {
        balanceElement.textContent = parseFloat(data.balance).toLocaleString() + ' ¥';
    }
    
    // 未実現損益の更新
    const unrealizedPLElement = document.getElementById('unrealized-pl');
    if (unrealizedPLElement && data.unrealized_pl !== undefined) {
        const value = parseFloat(data.unrealized_pl);
        unrealizedPLElement.textContent = value.toLocaleString() + ' ¥';
        
        if (value > 0) {
            unrealizedPLElement.classList.add('text-success');
            unrealizedPLElement.classList.remove('text-danger');
        } else if (value < 0) {
            unrealizedPLElement.classList.add('text-danger');
            unrealizedPLElement.classList.remove('text-success');
        } else {
            unrealizedPLElement.classList.remove('text-success', 'text-danger');
        }
    }
    
    // 実現損益の更新
    const realizedPLElement = document.getElementById('realized-pl');
    if (realizedPLElement && data.realized_pl !== undefined) {
        const value = parseFloat(data.realized_pl);
        realizedPLElement.textContent = value.toLocaleString() + ' ¥';
        
        if (value > 0) {
            realizedPLElement.classList.add('text-success');
            realizedPLElement.classList.remove('text-danger');
        } else if (value < 0) {
            realizedPLElement.classList.add('text-danger');
            realizedPLElement.classList.remove('text-success');
        } else {
            realizedPLElement.classList.remove('text-success', 'text-danger');
        }
    }
    
    // 勝率の更新
    const winRateElement = document.getElementById('win-rate');
    if (winRateElement && data.win_rate !== undefined) {
        winRateElement.textContent = data.win_rate + '%';
    }
    
    // 最近の取引の更新
    updateRecentTrades(data.recent_trades || []);
}

/**
 * 最近の取引を更新する
 */
function updateRecentTrades(trades) {
    const tableBody = document.getElementById('recent-trades-tbody');
    if (!tableBody) return;
    
    // テーブルをクリア
    tableBody.innerHTML = '';
    
    if (trades.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 9;
        cell.className = 'text-center';
        cell.textContent = '取引データがありません';
        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
    }
    
    // 取引データを追加
    trades.forEach(trade => {
        const row = document.createElement('tr');
        
        // ID
        const idCell = document.createElement('td');
        const idLink = document.createElement('a');
        idLink.href = `/dashboard/trade/${trade.id}`;
        idLink.textContent = `#${trade.id}`;
        idCell.appendChild(idLink);
        row.appendChild(idCell);
        
        // 日時
        const dateCell = document.createElement('td');
        dateCell.textContent = new Date(trade.timestamp).toLocaleString();
        row.appendChild(dateCell);
        
        // 通貨ペア
        const pairCell = document.createElement('td');
        pairCell.textContent = trade.currency_pair;
        row.appendChild(pairCell);
        
        // タイプ
        const typeCell = document.createElement('td');
        const typeSpan = document.createElement('span');
        typeSpan.className = `badge bg-${trade.trade_type === 'buy' ? 'success' : 'danger'}`;
        typeSpan.textContent = trade.trade_type === 'buy' ? '買い' : '売り';
        typeCell.appendChild(typeSpan);
        row.appendChild(typeCell);
        
        // 価格
        const priceCell = document.createElement('td');
        priceCell.textContent = parseFloat(trade.price).toLocaleString() + ' ¥';
        row.appendChild(priceCell);
        
        // 数量
        const amountCell = document.createElement('td');
        amountCell.textContent = parseFloat(trade.amount).toFixed(4);
        row.appendChild(amountCell);
        
        // ステータス
        const statusCell = document.createElement('td');
        const statusSpan = document.createElement('span');
        let statusClass, statusText;
        
        switch (trade.status) {
            case 'open':
                statusClass = 'primary';
                statusText = 'オープン';
                break;
            case 'closed':
                statusClass = 'secondary';
                statusText = 'クローズド';
                break;
            default:
                statusClass = 'warning';
                statusText = trade.status;
        }
        
        statusSpan.className = `badge bg-${statusClass}`;
        statusSpan.textContent = statusText;
        statusCell.appendChild(statusSpan);
        row.appendChild(statusCell);
        
        // 損益
        const plCell = document.createElement('td');
        if (trade.profit_loss !== null && trade.profit_loss !== undefined) {
            const plValue = parseFloat(trade.profit_loss);
            plCell.textContent = plValue.toLocaleString() + ' ¥';
            
            if (plValue > 0) {
                plCell.className = 'text-success';
            } else if (plValue < 0) {
                plCell.className = 'text-danger';
            }
        } else {
            plCell.textContent = '-';
        }
        row.appendChild(plCell);
        
        // アクション
        const actionCell = document.createElement('td');
        if (trade.status === 'open') {
            const closeBtn = document.createElement('button');
            closeBtn.className = 'btn btn-sm btn-warning close-trade-btn';
            closeBtn.setAttribute('data-trade-id', trade.id);
            closeBtn.textContent = 'クローズ';
            actionCell.appendChild(closeBtn);
        } else {
            const detailsBtn = document.createElement('a');
            detailsBtn.href = `/dashboard/trade/${trade.id}`;
            detailsBtn.className = 'btn btn-sm btn-info';
            detailsBtn.textContent = '詳細';
            actionCell.appendChild(detailsBtn);
        }
        row.appendChild(actionCell);
        
        tableBody.appendChild(row);
    });
}

/**
 * ティッカー情報を更新する
 */
function updateTickerInfo() {
    fetch('/api/dashboard/ticker')
        .then(response => response.json())
        .then(data => {
            const tickerElement = document.getElementById('ticker-price');
            if (tickerElement && data.last) {
                tickerElement.textContent = parseFloat(data.last).toLocaleString() + ' ¥';
            }
        })
        .catch(error => {
            console.error('ティッカー情報の取得エラー:', error);
        });
}

/**
 * 取引確認を準備する
 */
function prepareTradeConfirmation(type) {
    const tradeTypeText = document.getElementById('trade-type-text');
    const tradeSymbolText = document.getElementById('trade-symbol-text');
    const tradeAmountInput = document.getElementById('trade-amount');
    
    if (tradeTypeText && tradeSymbolText) {
        tradeTypeText.textContent = type === 'buy' ? '買い' : '売り';
        tradeSymbolText.textContent = currentSymbol;
    }
    
    if (tradeConfirmModal) {
        tradeConfirmModal.show();
    }
}

/**
 * 取引を実行する
 */
function executeTrade() {
    const amount = document.getElementById('trade-amount').value;
    const type = document.getElementById('trade-type-text').textContent === '買い' ? 'buy' : 'sell';
    
    if (!amount || isNaN(amount) || parseFloat(amount) <= 0) {
        showError('有効な取引量を入力してください');
        return;
    }
    
    fetch('/api/dashboard/manual-trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            trade_type: type,
            symbol: currentSymbol,
            amount: parseFloat(amount)
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showError(data.error);
        } else {
            showSuccess('取引が正常に実行されました');
            
            // データを更新
            loadChartData(currentSymbol, currentInterval);
            loadTradeStats();
        }
        
        // モーダルを閉じる
        if (tradeConfirmModal) {
            tradeConfirmModal.hide();
        }
    })
    .catch(error => {
        showError('取引の実行中にエラーが発生しました');
        console.error('取引エラー:', error);
    });
}

/**
 * トレードを閉じる
 */
function closeTrade(tradeId) {
    fetch(`/api/dashboard/close-trade/${tradeId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showError(data.error);
        } else {
            showSuccess('トレードが正常に閉じられました');
            
            // データを更新
            loadChartData(currentSymbol, currentInterval);
            loadTradeStats();
        }
        
        // モーダルを閉じる
        if (closeTradeModal) {
            closeTradeModal.hide();
        }
    })
    .catch(error => {
        showError('トレードを閉じる際にエラーが発生しました');
        console.error('トレードを閉じるエラー:', error);
    });
}

/**
 * ローディングを表示する
 */
function showLoading(message) {
    // トーストメッセージでローディング表示
    const toastContainer = document.getElementById('toast-container');
    if (toastContainer) {
        const toast = document.createElement('div');
        toast.className = 'toast show loading-toast';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="toast-header bg-primary text-white">
                <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                <strong class="me-auto">読み込み中</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">${message || 'データを読み込んでいます...'}</div>
        `;
        
        toastContainer.appendChild(toast);
        
        // 5秒後に自動で閉じる
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    }
}

/**
 * ローディングを非表示にする
 */
function hideLoading() {
    const loadingToasts = document.querySelectorAll('.loading-toast');
    loadingToasts.forEach(toast => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 500);
    });
}

/**
 * エラーメッセージを表示する
 */
function showError(message) {
    const toastContainer = document.getElementById('toast-container');
    if (toastContainer) {
        const toast = document.createElement('div');
        toast.className = 'toast show';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="toast-header bg-danger text-white">
                <i class="fas fa-exclamation-circle me-2"></i>
                <strong class="me-auto">エラー</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">${message}</div>
        `;
        
        toastContainer.appendChild(toast);
        
        // 5秒後に自動で閉じる
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    }
}

/**
 * 成功メッセージを表示する
 */
function showSuccess(message) {
    const toastContainer = document.getElementById('toast-container');
    if (toastContainer) {
        const toast = document.createElement('div');
        toast.className = 'toast show';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="toast-header bg-success text-white">
                <i class="fas fa-check-circle me-2"></i>
                <strong class="me-auto">成功</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">${message}</div>
        `;
        
        toastContainer.appendChild(toast);
        
        // 5秒後に自動で閉じる
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    }
}