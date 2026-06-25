import { Component, OnInit, OnDestroy, AfterViewChecked, ViewChild, ElementRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService, Signal, GateEntry, OhlcvBar } from '../../services/api.service';
import { createChart, LineStyle } from 'lightweight-charts';

export interface GateSection {
  title: string;
  entries: GateEntry[];
}

// ── helpers: moving-average computation ──────────────────────────────────────

function sma(values: number[], period: number): (number | null)[] {
  return values.map((_, i) => {
    if (i < period - 1) return null;
    return values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period;
  });
}

function ema(values: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const result: (number | null)[] = new Array(values.length).fill(null);
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i === period - 1) {
      result[i] = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
      prev = result[i];
    } else if (i > period - 1) {
      result[i] = values[i] * k + prev! * (1 - k);
      prev = result[i];
    }
  }
  return result;
}

// ─────────────────────────────────────────────────────────────────────────────

@Component({
  selector: 'app-diagnosis',
  templateUrl: './diagnosis.component.html',
  styleUrls: ['./diagnosis.component.css']
})
export class DiagnosisComponent implements OnInit, OnDestroy, AfterViewChecked {
  signal: Signal | null = null;
  sections: GateSection[] = [];
  loading = true;
  notFound = false;

  // On-demand diagnose state (shown when no :id in route)
  onDemand = false;
  onDemandTicker = '';
  onDemandStrategy = 'pullback';
  jobStatus: 'idle' | 'queued' | 'running' | 'done' | 'error' = 'idle';
  jobError: string | null = null;

  accountSize = 6500;
  riskPct = 1;

  // Chart (E12.7)
  ohlcv: OhlcvBar[] = [];
  @ViewChild('chartContainer') chartContainer?: ElementRef;
  private _lc: ReturnType<typeof createChart> | null = null;
  private _chartNeeded = false;

  private _pollTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private route: ActivatedRoute, private api: ApiService) {}

  ngOnInit(): void {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (!idParam) {
      this.onDemand = true;
      this.loading = false;
      return;
    }
    const id = Number(idParam);
    if (isNaN(id)) { this.notFound = true; this.loading = false; return; }
    this._loadSignal(id);
  }

  ngAfterViewChecked(): void {
    if (this._chartNeeded && this.chartContainer?.nativeElement) {
      this._chartNeeded = false;
      this._renderChart();
    }
  }

  ngOnDestroy(): void {
    if (this._pollTimer) clearTimeout(this._pollTimer);
    if (this._lc) { this._lc.remove(); this._lc = null; }
  }

  private _loadSignal(id: number): void {
    this.api.getSignal(id).subscribe(s => {
      this.signal = s;
      this.notFound = s === null;
      if (s?.gate_detail) this.sections = this._buildSections(s.gate_detail);
      this.loading = false;
      if (s?.ticker) {
        this.api.getOhlcv(s.ticker).subscribe(res => {
          if (res && res.bars.length) {
            this.ohlcv = res.bars;
            this._chartNeeded = true;
          }
        });
      }
    });
  }

  startDiagnose(): void {
    const ticker = this.onDemandTicker.trim().toUpperCase();
    if (!ticker) return;
    this.jobStatus = 'queued';
    this.jobError = null;
    this.signal = null;
    this.sections = [];
    this.ohlcv = [];
    if (this._lc) { this._lc.remove(); this._lc = null; }

    this.api.postJob('diagnose', { ticker, strategy: this.onDemandStrategy }).subscribe(res => {
      if (!res) {
        this.jobStatus = 'error';
        this.jobError = 'Failed to enqueue job — is the API running?';
        return;
      }
      this._pollJob(res.id);
    });
  }

  private _pollJob(jobId: number): void {
    this.api.pollJob(jobId).subscribe(job => {
      if (!job) {
        this.jobStatus = 'error';
        this.jobError = 'Lost contact with the API.';
        return;
      }
      this.jobStatus = job.status as typeof this.jobStatus;

      if (job.status === 'done' && job.result_ref) {
        this._loadSignal(Number(job.result_ref));
      } else if (job.status === 'error') {
        this.jobError = job.result_ref || 'Worker reported an error.';
      } else {
        this._pollTimer = setTimeout(() => this._pollJob(jobId), 1500);
      }
    });
  }

  private _buildSections(entries: GateEntry[]): GateSection[] {
    const sections: GateSection[] = [];
    let current: GateSection = { title: '', entries: [] };
    for (const e of entries) {
      if (e.status === 'section') {
        if (current.title || current.entries.length) sections.push(current);
        current = { title: e.name, entries: [] };
      } else {
        current.entries.push(e);
      }
    }
    if (current.title || current.entries.length) sections.push(current);
    return sections;
  }

  private _renderChart(): void {
    if (this._lc) { this._lc.remove(); this._lc = null; }
    const el = this.chartContainer!.nativeElement as HTMLElement;
    if (!el || !this.ohlcv.length) return;

    try {
      const chart = createChart(el, {
        width: el.offsetWidth || 800,
        height: 280,
        layout: {
          background: { color: '#0d0d1a' },
          textColor: '#808090',
        },
        grid: {
          vertLines: { color: '#1a1a2e' },
          horzLines: { color: '#1a1a2e' },
        },
        timeScale: { borderColor: '#2a2a4a' },
        rightPriceScale: { borderColor: '#2a2a4a' },
        crosshair: { mode: 0 },
      });
      this._lc = chart;

      // Candlestick series
      const candles = chart.addCandlestickSeries({
        upColor: '#4caf89',
        downColor: '#c46060',
        borderVisible: false,
        wickUpColor: '#4caf89',
        wickDownColor: '#c46060',
      });
      candles.setData(this.ohlcv.map(b => ({
        time: b.date as `${number}-${number}-${number}`,
        open: b.open, high: b.high, low: b.low, close: b.close,
      })));

      // Stop / target price lines
      const sig = this.signal;
      if (sig?.stop) {
        candles.createPriceLine({
          price: sig.stop,
          color: '#c46060',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'Stop',
        });
      }
      if (sig?.target) {
        candles.createPriceLine({
          price: sig.target,
          color: '#4caf89',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'Target',
        });
      }

      // Moving averages computed client-side
      const closes = this.ohlcv.map(b => b.close);
      const dates = this.ohlcv.map(b => b.date as `${number}-${number}-${number}`);

      const addLine = (vals: (number | null)[], color: string, title: string, width = 1) => {
        const series = chart.addLineSeries({
          color, lineWidth: width as 1 | 2 | 3 | 4,
          title, lastValueVisible: false, priceLineVisible: false,
        });
        series.setData(
          vals.map((v, i) => v !== null ? { time: dates[i], value: v } : null)
              .filter((x): x is { time: `${number}-${number}-${number}`; value: number } => x !== null)
        );
      };

      addLine(sma(closes, 20), '#808090', 'SMA20');
      addLine(sma(closes, 50), '#3a6abf', 'SMA50');
      addLine(ema(closes, 20), '#bf8a3a', 'EMA20');

      chart.timeScale().fitContent();
    } catch (_) {
      // Chart lib unavailable in test environments — graceful no-op
    }
  }

  // ── positioning ───────────────────────────────────────────────────────────

  get shares(): number {
    const s = this.signal;
    if (!s?.close || !s?.stop) return 0;
    const riskDollars = this.accountSize * (this.riskPct / 100);
    const perShare = s.close - s.stop;
    if (perShare <= 0) return 0;
    const maxShares = Math.floor((this.accountSize * 0.1) / s.close);
    return Math.min(Math.floor(riskDollars / perShare), maxShares);
  }

  get riskDollars(): number {
    return this.shares * ((this.signal?.close ?? 0) - (this.signal?.stop ?? 0));
  }

  get rr(): string {
    const s = this.signal;
    if (!s?.close || !s?.stop || !s?.target) return '—';
    const r = (s.target - s.close) / (s.close - s.stop);
    return isFinite(r) ? r.toFixed(2) + 'R' : '—';
  }

  get positionValue(): number {
    return this.shares * (this.signal?.close ?? 0);
  }

  get stopDistance(): string {
    const s = this.signal;
    if (!s?.close || !s?.stop) return '—';
    return ((s.close - s.stop) / s.close * 100).toFixed(1) + '%';
  }

  activeHint: string | null = null;

  toggleHint(name: string, event: Event): void {
    event.stopPropagation();
    this.activeHint = this.activeHint === name ? null : name;
  }

  hintFor(name: string): string | null {
    if (GATE_HINTS[name]) return GATE_HINTS[name];
    for (const key of Object.keys(GATE_HINTS)) {
      if (name.startsWith(key)) return GATE_HINTS[key];
    }
    return null;
  }

  gateStatusClass(entry: GateEntry): string {
    if (entry.status === 'pass' || entry.status === 'bonus_pass') return 'g-pass';
    if (entry.status === 'fail' || entry.status === 'bonus_fail') return 'g-fail';
    return 'g-skip';
  }

  gateIcon(entry: GateEntry): string {
    if (entry.status === 'pass' || entry.status === 'bonus_pass') return '✓';
    if (entry.status === 'fail' || entry.status === 'bonus_fail') return '✗';
    return '–';
  }

  isBonus(entry: GateEntry): boolean {
    return entry.status === 'bonus_pass' || entry.status === 'bonus_fail';
  }

  failedCount(): number {
    const fg = this.signal?.failed_gates ?? '';
    return fg ? fg.split(';').filter(g => g.trim()).length : 0;
  }
}

const GATE_HINTS: Record<string, string> = {
  // ── Trend context ──────────────────────────────────────────────────────────
  'Uptrend (SMA50 > SMA200)':
    'The 50-day MA must be above the 200-day MA — the classic confirmation that the long-term trend is up. Buying pullbacks in a downtrend is catching a falling knife; this ensures the trend is your ally.',

  'SMA50 rising':
    'The 50-day MA must be trending upward over the past 20 sessions. A flat or declining SMA50 means momentum has stalled even if the MA is still above the 200-MA — you want acceleration, not drift.',

  'Near 52w high':
    'The stock must have been near its 52-week high recently. Leaders make new highs, then pull back. If the 52-week high was more than 90 days ago the setup has gone stale and the stock may be a laggard.',

  '200-MA distance in range':
    'Price should not be too far above the 200-day MA. Stocks that have stretched far from it tend to mean-revert rather than continue. This keeps you out of overextended names where the risk/reward is poor.',

  // ── Pullback structure ─────────────────────────────────────────────────────
  'Pullback duration':
    'The pullback must last 3–20 sessions. Too short means no real reset — just noise. Too long (more than 4 weeks) suggests the stock may be breaking down rather than consolidating. The sweet spot captures natural profit-taking.',

  'Pullback depth':
    'Price must have retraced 4–18% from the recent swing high. Too shallow (< 4%) means buyers never gave ground — likely just noise. Too deep (> 18%) suggests the stock may be breaking down rather than consolidating.',

  'Swing low intact':
    'The current pullback low must stay above the most recent prior swing low. A breach creates a lower low — the textbook definition of a downtrend — and invalidates the bullish structure entirely.',

  'Volume contraction':
    'Volume during the pullback should be declining, showing sellers losing conviction. Expanding volume on a pullback signals active distribution by institutions, not routine profit-taking by weaker hands.',

  'At a logical support level':
    'Entry near a known support (EMA20, SMA50, prior swing high-turned-support, etc.) gives you a tight, logical stop just below it. Buying in the middle of open air means a wider stop and worse risk/reward.',

  'At ':
    'Price is currently testing a specific support level, giving you a precise stop placement just below it. The closer you enter to support, the smaller the risk and the better the reward-to-risk ratio.',

  // ── Momentum ───────────────────────────────────────────────────────────────
  'RSI(14) reset':
    'RSI must be between 40–60 — momentum cooled during the pullback without crossing into oversold. RSI above 60 means no real pullback occurred; below 40 suggests potential trend damage rather than healthy consolidation.',

  'RSI in breakout range':
    'RSI must be 55–75 — enough momentum to push through resistance without being overbought. Below 55 = weak buying pressure; above 75 = the move may already be exhausted before you enter.',

  'ADX(14) trend strength':
    'ADX above 20 confirms a trending environment. Low ADX means the stock is range-bound or choppy — pullback setups in choppy conditions tend to oscillate rather than resolve in the trend direction.',

  'ADX trend strength':
    'ADX ≥ 20 confirms trend strength heading into the breakout. Breakouts from low-ADX, sideways environments fail far more often — you want the market already in motion when you add momentum to it.',

  // ── Quality gates ──────────────────────────────────────────────────────────
  'Earnings clear':
    'No earnings report within 7 days. An earnings release can gap the stock past your stop overnight, turning a controlled-risk trade into an open-ended loss. This filter eliminates binary events within your typical holding window.',

  'Relative strength vs SPY':
    'The stock must be outperforming the S&P 500 by a minimum threshold. Stocks with weak relative strength are underperformers — they lag the market on the way up and lead it on the way down.',

  'Sector ':
    'The sector ETF must be above its 50-day MA. Even a fundamentally strong stock faces headwinds when its entire sector is under institutional distribution. Sector tailwinds multiply individual name strength.',

  'Weekly above 30-MA':
    'The weekly close must be above the 30-week moving average. This filters out daily-chart setups occurring within a larger weekly downtrend — one of the most common traps for technically-minded traders.',

  'Liquidity':
    'Average daily dollar volume ≥ $5 million. Below this threshold, bid-ask spreads widen, fill quality degrades, and exiting a position can move the price against you. Liquidity is non-negotiable for stops to work.',

  'Market cap in range':
    'Market cap between $300M and $50B — mid-cap territory. Below $300M: too illiquid and prone to erratic moves. Above $50B: too mature and widely-owned for the explosive momentum moves this strategy targets.',

  'Profitable':
    'The company must have positive trailing-twelve-month earnings. Unprofitable companies carry binary survival risk — a bad quarter can trigger a re-rating that blows through any technical stop you set.',

  'Debt/equity acceptable':
    'Debt-to-equity ratio below the threshold. High leverage amplifies downside. In a sell-off, heavily indebted companies face credit concerns layered on top of the price decline, creating uncontrollable risk.',

  // ── Breakout-specific ──────────────────────────────────────────────────────
  'Consolidation breakout':
    'Close must be above the highest high of the prior 20-session consolidation range. This proves the stock absorbed overhead supply during base-building and buyers are now in control — the textbook VCP or cup-and-handle breakout.',

  'Volume confirmation':
    'Breakout volume ≥ 1.5× the 50-day average. A price breakout on low volume is a fake-out — institutions weren\'t participating and the move will likely fail. Heavy volume proves large players are stepping in.',

  'Trend alignment':
    'Close > SMA50 > SMA200 — all three levels stacked in bullish order. Breaking out within a structurally healthy trend means you have the long-term current behind you, not fighting against it.',

  'BB squeeze':
    'Bollinger Band width in the lowest 40th percentile of the trailing 60 days. Periods of extreme volatility compression are reliably followed by expansion moves. You\'re entering just as the spring is most tightly coiled.',

  // ── Bonus gates (add to score, never eliminate) ───────────────────────────
  'Bullish reversal candle':
    'Bonus. Last bar is a hammer, engulfing, or doji at support — buyers stepped in intra-day to defend the level. Not required, but adds conviction that the pullback low is holding.',

  'Pocket Pivot trigger':
    'Bonus. Volume on this up-day exceeds all down-day volumes in the prior 10 sessions. Developed by Chris Kacher — signals quiet institutional accumulation during the base, before the public move.',

  'NR7 contraction':
    'Bonus. Today\'s price range is the narrowest of the past 7 sessions. Extreme range contraction signals energy being coiled. This compression pattern often precedes a sharp, clean directional move.',

  'RS line at 60d high':
    'Bonus. The relative strength line vs SPY is at a 60-day high. The stock is demonstrating market leadership even while it pulls back — a sign that institutions are defending positions.',

  'Sector outperforming SPY':
    'Bonus. The sector ETF has outperformed SPY over the past 20 days. Sector rotation is a powerful force — being positioned in the leading sector adds a meaningful tailwind on top of the individual setup.',

  'Weekly 30-MA rising':
    'Bonus. The 30-week moving average is itself trending upward — not just intact, but accelerating. The strongest setups show a rising long-term average being tested from above, not a flat or declining one.',

  '200-MA in sweet spot':
    'Bonus. Price is 5–40% above the 200-day MA. In this zone the stock is trending well without being dangerously extended. Beyond 40% above the 200-MA, mean-reversion risk rises sharply.',
};
