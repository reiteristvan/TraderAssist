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
