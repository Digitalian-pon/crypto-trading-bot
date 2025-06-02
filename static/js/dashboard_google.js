// Google Charts を使用したダッシュボード
let currentSymbol = 'XRP_JPY';
let currentInterval = '5min';

// Google Charts ライブラリの読み込み
google.charts.load('current', {'packages':['corechart', 'line']});

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    console.log("ダッシュボード初期化開始");
    
    // Google Charts の準備ができたら初期化
    google.charts.setOnLoadCallback(initDashboard);
});

function initDashboard() {
    console.log("Google Charts 準備完了");
    
    // イベントリスナーの設定
    setupEventListeners();
    
    // データ読み込み
    loadChartData(currentSymbol, currentInterval);
    loadTradeStats();
    
    console.log("ダッシュボード初期化完了");
}

// イベントリスナーの設定
function setupEventListeners() {
    // 通貨ペア選択（複数のIDに対応）
    const symbolSelects = ['symbol-select', 'chart-symbol-select'];
    symbolSelects.forEach(id => {
        const symbolSelect = document.getElementById(id);
        if (symbolSelect) {
            symbolSelect.addEventListener('change', function() {
                currentSymbol = this.value;
                console.log(`通貨ペア変更: ${currentSymbol}`);
                loadChartData(currentSymbol, currentInterval);
            });
        }
    });
    
    // チャート更新ボタン
    const refreshBtn = document.getElementById('refresh-chart-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            console.log('チャート更新ボタンがクリックされました');
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 更新中...';
            this.disabled = true;
            
            loadChartData(currentSymbol, currentInterval, false).finally(() => {
                this.innerHTML = '<i class="fas fa-sync-alt me-1"></i> チャート更新';
                this.disabled = false;
            });
        });
    }
    
    // 新データ取得ボタン
    const forceRefreshBtn = document.getElementById('force-refresh-btn');
    if (forceRefreshBtn) {
        forceRefreshBtn.addEventListener('click', function() {
            console.log('新データ取得ボタンがクリックされました');
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 取得中...';
            this.disabled = true;
            
            loadChartData(currentSymbol, currentInterval, true).finally(() => {
                this.innerHTML = '<i class="fas fa-download me-1"></i> 新データ取得';
                this.disabled = false;
            });
        });
    }
    
    // 時間足ボタン
    document.querySelectorAll('.interval-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // アクティブ状態の切り替え
            document.querySelectorAll('.interval-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            currentInterval = this.dataset.interval;
            console.log(`時間足変更: ${currentInterval}`);
            loadChartData(currentSymbol, currentInterval);
        });
    });
    
    // テクニカル指標チェックボックス
    const indicatorCheckboxes = ['sma', 'ema', 'bollinger', 'rsi', 'macd', 'volume'];
    indicatorCheckboxes.forEach(indicator => {
        const checkbox = document.getElementById(indicator + '-check');
        if (checkbox) {
            checkbox.addEventListener('change', function() {
                console.log(`テクニカル指標 ${indicator} ${this.checked ? '有効' : '無効'}`);
                loadChartData(currentSymbol, currentInterval);
            });
        }
    });
}

// チャートデータの読み込み
function loadChartData(symbol, interval, forceRefresh = false) {
    console.log(`チャートデータ読み込み: ${symbol}, ${interval}, 強制更新: ${forceRefresh}`);
    
    showLoadingIndicator();
    
    const url = `/api/dashboard/chart-data?symbol=${symbol}&interval=${interval}` + 
                (forceRefresh ? '&force_refresh=true' : '');
    
    return fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('チャートデータ取得成功');
            renderGoogleChart(data);
        })
        .catch(error => {
            console.error('エラー:', error);
            displayChartError('データの取得に失敗しました');
        })
        .finally(() => {
            hideLoadingIndicator();
        });
}

// Google Charts でチャートを描画
function renderGoogleChart(data) {
    console.log('Google Charts でチャート描画開始');
    console.log('受信データ:', data);
    
    if (!data.timestamps || !data.prices || data.timestamps.length === 0) {
        console.error('データが不正です:', data);
        displayChartError('有効なデータがありません');
        return;
    }
    
    // チャート要素の存在確認
    const chartElement = document.getElementById('priceChart');
    if (!chartElement) {
        console.error('チャート要素が見つかりません: priceChart');
        displayChartError('チャート要素が見つかりません');
        return;
    }
    
    console.log('チャート要素を確認:', chartElement);
    
    // 価格データの構造を確認
    let priceData = null;
    if (data.prices && typeof data.prices === 'object') {
        // 構造化された価格データ（close価格を使用）
        priceData = data.prices.close || data.prices.open || data.prices.high || data.prices.low;
    } else if (Array.isArray(data.prices)) {
        // 単純な配列
        priceData = data.prices;
    }
    
    console.log('価格データタイプ:', typeof data.prices);
    console.log('データ点数:', data.timestamps ? data.timestamps.length : 0, priceData ? priceData.length : 0);
    
    if (!priceData || priceData.length === 0) {
        console.error('有効な価格データがありません');
        displayChartError('価格データが見つかりません');
        return;
    }
    
    // データを Google Charts 形式に変換
    const chartData = new google.visualization.DataTable();
    chartData.addColumn('string', '時間');
    chartData.addColumn('number', '価格');
    
    // テクニカル指標の追加
    const selectedIndicators = getSelectedIndicators();
    console.log('選択されたテクニカル指標:', selectedIndicators);
    console.log('利用可能な指標:', Object.keys(data.indicators));
    
    if (selectedIndicators.includes('sma') && data.indicators.sma) {
        console.log('SMA指標を追加中');
        if (data.indicators.sma.sma_20) chartData.addColumn('number', 'SMA20');
        if (data.indicators.sma.sma_50) chartData.addColumn('number', 'SMA50');
    }
    
    if (selectedIndicators.includes('ema') && data.indicators.ema) {
        if (data.indicators.ema.ema_20) chartData.addColumn('number', 'EMA20');
        if (data.indicators.ema.ema_50) chartData.addColumn('number', 'EMA50');
    }
    
    if (selectedIndicators.includes('bollinger') && data.indicators.bollinger) {
        chartData.addColumn('number', 'BB上限');
        chartData.addColumn('number', 'BB中央');
        chartData.addColumn('number', 'BB下限');
    }
    
    // RSI、MACD、出来高は価格軸と異なるスケールのため、価格チャートには表示しない
    // （別のチャートエリアが必要）
    console.log('RSI、MACD、出来高は価格チャートとは別の表示が必要です');
    
    // データ追加
    const rows = [];
    for (let i = 0; i < Math.min(data.timestamps.length, priceData.length); i++) {
        if (priceData[i] != null && !isNaN(priceData[i])) {
            const timeStr = new Date(data.timestamps[i]).toLocaleTimeString('ja-JP', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            const row = [timeStr, parseFloat(priceData[i])];
            
            // テクニカル指標データの追加
            if (selectedIndicators.includes('sma') && data.indicators.sma) {
                if (data.indicators.sma.sma_20) row.push(data.indicators.sma.sma_20[i] || null);
                if (data.indicators.sma.sma_50) row.push(data.indicators.sma.sma_50[i] || null);
            }
            
            if (selectedIndicators.includes('ema') && data.indicators.ema) {
                if (data.indicators.ema.ema_20) row.push(data.indicators.ema.ema_20[i] || null);
                if (data.indicators.ema.ema_50) row.push(data.indicators.ema.ema_50[i] || null);
            }
            
            if (selectedIndicators.includes('bollinger') && data.indicators.bollinger) {
                row.push(data.indicators.bollinger.upper[i] || null);
                row.push(data.indicators.bollinger.middle[i] || null);
                row.push(data.indicators.bollinger.lower[i] || null);
            }
            
            rows.push(row);
        }
    }
    
    chartData.addRows(rows);
    
    // チャートオプション
    const options = {
        title: `${currentSymbol.replace('_', '/')} 価格チャート`,
        titleTextStyle: {
            color: '#e0e0e0',
            fontSize: 16
        },
        backgroundColor: '#1e1e1e',
        chartArea: {
            left: 60,
            top: 60,
            width: '80%',
            height: '75%',
            backgroundColor: '#1e1e1e'
        },
        hAxis: {
            title: '時間',
            titleTextStyle: { color: '#e0e0e0' },
            textStyle: { color: '#b0b0b0' },
            gridlines: { color: '#404040' }
        },
        vAxis: {
            title: '価格 (¥)',
            titleTextStyle: { color: '#e0e0e0' },
            textStyle: { color: '#b0b0b0' },
            gridlines: { color: '#404040' }
        },
        legend: {
            position: 'top',
            textStyle: { color: '#e0e0e0' }
        },
        colors: getChartColors(selectedIndicators),
        lineWidth: 2,
        pointSize: 3
    };
    
    // チャート描画
    const chart = new google.visualization.LineChart(document.getElementById('priceChart'));
    
    try {
        console.log('チャート描画オプション:', options);
        console.log('チャートデータテーブル行数:', chartData.getNumberOfRows());
        
        chart.draw(chartData, options);
        console.log('Google Charts でチャート描画成功');
        console.log('チャート要素の内容:', chartElement.innerHTML.length > 0 ? 'あり' : 'なし');
        hideChartError();
        
        // RSI、MACD、出来高の別チャートを描画
        drawIndicatorCharts(data, selectedIndicators);
        
        // チャートが実際に描画されているか確認
        setTimeout(() => {
            console.log('描画後のチャート要素:', chartElement.innerHTML.substring(0, 100));
        }, 1000);
        
    } catch (error) {
        console.error('チャート描画エラー:', error);
        console.error('エラー詳細:', error.message, error.stack);
        displayChartError('チャートの描画に失敗しました: ' + error.message);
    }
}

// 統計データの読み込み
function loadTradeStats() {
    fetch('/api/dashboard/trade-stats')
        .then(response => response.json())
        .then(data => {
            updateTradeStats(data);
        })
        .catch(error => {
            console.error('統計取得エラー:', error);
        });
}

// 統計の更新
function updateTradeStats(data) {
    if (data.success) {
        const elements = {
            'active-trades-count': data.open_trades,
            'total-trades-count': data.total_trades,
            'total-pnl': data.total_pnl.toFixed(2) + '¥',
            'win-rate': data.win_rate.toFixed(1) + '%'
        };
        
        for (const [id, value] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        }
    }
}

// ローディング表示
function showLoadingIndicator() {
    const loadingEl = document.getElementById('chart-loading');
    if (loadingEl) {
        loadingEl.classList.remove('d-none');
    }
}

// ローディング非表示
function hideLoadingIndicator() {
    const loadingEl = document.getElementById('chart-loading');
    if (loadingEl) {
        loadingEl.classList.add('d-none');
    }
}

// エラー表示
function displayChartError(message) {
    const errorEl = document.getElementById('chart-error-message');
    if (errorEl) {
        errorEl.querySelector('span').textContent = message;
        errorEl.classList.remove('d-none');
    }
}

// エラー非表示
function hideChartError() {
    const errorEl = document.getElementById('chart-error-message');
    if (errorEl) {
        errorEl.classList.add('d-none');
    }
}

// 選択されたテクニカル指標を取得
function getSelectedIndicators() {
    const selected = [];
    const checkboxes = ['sma', 'ema', 'bollinger', 'rsi', 'macd', 'volume'];
    
    checkboxes.forEach(indicator => {
        const checkbox = document.getElementById(indicator + '-check');
        if (checkbox && checkbox.checked) {
            selected.push(indicator);
        }
    });
    
    return selected;
}

// チャートの色を設定
function getChartColors(selectedIndicators) {
    const colors = ['#00ff88']; // 価格線の色
    
    if (selectedIndicators.includes('sma')) {
        colors.push('#ff6b6b'); // SMA20
        colors.push('#4ecdc4'); // SMA50
    }
    
    if (selectedIndicators.includes('ema')) {
        colors.push('#45b7d1'); // EMA20
        colors.push('#f9ca24'); // EMA50
    }
    
    if (selectedIndicators.includes('bollinger')) {
        colors.push('#dda0dd'); // BB上限
        colors.push('#98fb98'); // BB中央
        colors.push('#dda0dd'); // BB下限
    }
    
    return colors;
}

// RSI、MACD、出来高の別チャートを描画
function drawIndicatorCharts(data, selectedIndicators) {
    // RSIチャートの描画
    if (selectedIndicators.includes('rsi') && data.indicators.rsi) {
        drawRSIChart(data);
    }
    
    // MACDチャートの描画  
    if (selectedIndicators.includes('macd') && data.indicators.macd) {
        drawMACDChart(data);
    }
    
    // 出来高チャートの描画
    if (selectedIndicators.includes('volume') && data.volume) {
        console.log('出来高チャート描画開始', data.volume.length);
        drawVolumeChart(data);
    } else if (selectedIndicators.includes('volume')) {
        console.log('出来高データが見つかりません:', data.volume ? 'データあり' : 'データなし');
    }
}

// RSIチャートの描画
function drawRSIChart(data) {
    const rsiElement = document.getElementById('rsiChart');
    if (!rsiElement) {
        console.log('RSIチャート要素が見つかりません');
        return;
    }
    
    const rsiData = new google.visualization.DataTable();
    rsiData.addColumn('string', '時間');
    rsiData.addColumn('number', 'RSI');
    
    const rsiRows = [];
    for (let i = 0; i < data.timestamps.length; i++) {
        if (data.indicators.rsi[i] != null) {
            const timeStr = new Date(data.timestamps[i]).toLocaleTimeString('ja-JP', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            rsiRows.push([timeStr, parseFloat(data.indicators.rsi[i])]);
        }
    }
    
    rsiData.addRows(rsiRows);
    
    const rsiOptions = {
        title: 'RSI (14)',
        titleTextStyle: { color: '#e0e0e0', fontSize: 14 },
        backgroundColor: '#1e1e1e',
        chartArea: { left: 60, top: 30, width: '80%', height: '70%', backgroundColor: '#1e1e1e' },
        hAxis: { textStyle: { color: '#b0b0b0' }, gridlines: { color: '#404040' } },
        vAxis: { 
            textStyle: { color: '#b0b0b0' }, 
            gridlines: { color: '#404040' },
            min: 0, 
            max: 100
        },
        legend: { position: 'none' },
        colors: ['#ffd700'],
        lineWidth: 2,
        height: 150
    };
    
    const rsiChart = new google.visualization.LineChart(rsiElement);
    rsiChart.draw(rsiData, rsiOptions);
    console.log('RSIチャート描画完了');
}

// MACDチャートの描画
function drawMACDChart(data) {
    const macdElement = document.getElementById('macdChart');
    if (!macdElement) {
        console.log('MACDチャート要素が見つかりません');
        return;
    }
    
    const macdData = new google.visualization.DataTable();
    macdData.addColumn('string', '時間');
    macdData.addColumn('number', 'MACD');
    macdData.addColumn('number', 'Signal');
    
    const macdRows = [];
    for (let i = 0; i < data.timestamps.length; i++) {
        if (data.indicators.macd.line[i] != null && data.indicators.macd.signal[i] != null) {
            const timeStr = new Date(data.timestamps[i]).toLocaleTimeString('ja-JP', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            macdRows.push([
                timeStr, 
                parseFloat(data.indicators.macd.line[i]),
                parseFloat(data.indicators.macd.signal[i])
            ]);
        }
    }
    
    macdData.addRows(macdRows);
    
    const macdOptions = {
        title: 'MACD',
        titleTextStyle: { color: '#e0e0e0', fontSize: 14 },
        backgroundColor: '#1e1e1e',
        chartArea: { left: 60, top: 30, width: '80%', height: '70%', backgroundColor: '#1e1e1e' },
        hAxis: { textStyle: { color: '#b0b0b0' }, gridlines: { color: '#404040' } },
        vAxis: { textStyle: { color: '#b0b0b0' }, gridlines: { color: '#404040' } },
        legend: { position: 'top', textStyle: { color: '#e0e0e0' } },
        colors: ['#00bfff', '#ff69b4'],
        lineWidth: 2,
        height: 200
    };
    
    const macdChart = new google.visualization.LineChart(macdElement);
    macdChart.draw(macdData, macdOptions);
    console.log('MACDチャート描画完了');
}

// 出来高チャートの描画
function drawVolumeChart(data) {
    const volumeElement = document.getElementById('volumeChart');
    if (!volumeElement) {
        console.log('出来高チャート要素が見つかりません');
        return;
    }
    
    const volumeData = new google.visualization.DataTable();
    volumeData.addColumn('string', '時間');
    volumeData.addColumn('number', '出来高');
    
    const volumeRows = [];
    for (let i = 0; i < data.timestamps.length; i++) {
        if (data.volume[i] != null) {
            const timeStr = new Date(data.timestamps[i]).toLocaleTimeString('ja-JP', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            volumeRows.push([timeStr, parseFloat(data.volume[i])]);
        }
    }
    
    volumeData.addRows(volumeRows);
    
    const volumeOptions = {
        title: '出来高',
        titleTextStyle: { color: '#e0e0e0', fontSize: 14 },
        backgroundColor: '#1e1e1e',
        chartArea: { left: 60, top: 30, width: '80%', height: '70%', backgroundColor: '#1e1e1e' },
        hAxis: { textStyle: { color: '#b0b0b0' }, gridlines: { color: '#404040' } },
        vAxis: { textStyle: { color: '#b0b0b0' }, gridlines: { color: '#404040' } },
        legend: { position: 'none' },
        colors: ['#32cd32'],
        lineWidth: 2,
        height: 200
    };
    
    const volumeChart = new google.visualization.ColumnChart(volumeElement);
    volumeChart.draw(volumeData, volumeOptions);
    console.log('出来高チャート描画完了');
}