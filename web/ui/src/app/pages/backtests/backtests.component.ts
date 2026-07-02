import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subject } from 'rxjs';
import { switchMap, takeUntil } from 'rxjs/operators';
import { ApiService, Run, CoreMetrics, ScoreBucket, ConfBucket, GateAttrib, TradeRecord, FailureAnalysis, StopOutForensics, TargetBucket, WlAnalysis } from '../../services/api.service';

@Component({
  selector: 'app-backtests',
  templateUrl: './backtests.component.html',
  styleUrls: ['./backtests.component.css']
})
export class BacktestsComponent implements OnInit, OnDestroy {
  runs: Run[] = [];
  selectedRun: Run | null = null;
  loading = true;
  detailLoading = false;
  loadError: string | null = null;
  private runId$ = new Subject<string>();
  private destroy$ = new Subject<void>();

  constructor(
    private api: ApiService,
    private route: ActivatedRoute,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.runId$.pipe(
      switchMap(id => this.api.getRun(id)),
      takeUntil(this.destroy$)
    ).subscribe({
      next: r => { this.selectedRun = r; this.detailLoading = false; this.loadError = null; },
      error: () => { this.selectedRun = null; this.detailLoading = false; this.loadError = 'Failed to load run details.'; }
    });

    this.api.getRuns('backtest').subscribe(r => {
      this.runs = r?.runs ?? [];
      this.loading = false;
      const runId = this.route.snapshot.paramMap.get('run_id');
      if (runId) this.selectRun(runId);
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  selectRun(runId: string): void {
    this.detailLoading = true;
    this.loadError = null;
    this.router.navigate(['/backtests', runId]);
    this.runId$.next(runId);
  }

  get coreMetrics(): CoreMetrics | null {
    return this.selectedRun?.metrics ?? null;
  }

  get scoreBuckets(): ScoreBucket[] {
    return this.selectedRun?.score_buckets ?? [];
  }

  get confBuckets(): ConfBucket[] {
    return this.selectedRun?.conf_buckets ?? [];
  }

  get gateAttribution(): GateAttrib[] {
    return this.selectedRun?.gate_attribution ?? [];
  }

  get trades(): TradeRecord[] {
    return this.selectedRun?.trades ?? [];
  }

  get failureAnalysis(): FailureAnalysis | null {
    return this.selectedRun?.failure_analysis ?? null;
  }

  get stopOutForensics(): StopOutForensics | null {
    return this.selectedRun?.stop_out_forensics ?? null;
  }

  branchClass(branch: string | null): string {
    if (branch === 'A') return 'branch-a';
    if (branch === 'B') return 'branch-b';
    return '';
  }

  get targetRBuckets(): TargetBucket[] {
    return this.selectedRun?.target_r_buckets ?? [];
  }

  get targetAtrBuckets(): TargetBucket[] {
    return this.selectedRun?.target_atr_buckets ?? [];
  }

  get hasTargetRData(): boolean {
    return this.targetRBuckets.some(b => b.n > 0);
  }

  get hasTargetAtrData(): boolean {
    return this.targetAtrBuckets.some(b => b.n > 0);
  }

  get wlAnalysis(): WlAnalysis | null {
    return this.selectedRun?.wl_analysis ?? null;
  }

  fmtWlValue(metric: string, value: number | null): string {
    if (value == null) return '—';
    switch (metric) {
      case 'RSI at entry':      return value.toFixed(1);
      case 'RVOL':              return value.toFixed(2) + 'x';
      case 'Pullback depth %':  return (value >= 0 ? '+' : '') + value.toFixed(1) + '%';
      case 'ATR multiple':      return value.toFixed(2);
      case 'Industry momentum': return (value >= 0 ? '+' : '') + value.toFixed(1) + '%';
      case 'Pct to 52w high':   return value.toFixed(1) + '%';
      default:                  return value.toFixed(2);
    }
  }

  fmtWlDelta(metric: string, delta: number | null): string {
    if (delta == null) return '—';
    const sign = delta >= 0 ? '+' : '';
    switch (metric) {
      case 'RSI at entry':      return sign + delta.toFixed(1);
      case 'RVOL':              return sign + delta.toFixed(2);
      case 'Pullback depth %':  return sign + delta.toFixed(1) + '%';
      case 'ATR multiple':      return sign + delta.toFixed(2);
      case 'Industry momentum': return sign + delta.toFixed(1) + '%';
      case 'Pct to 52w high':   return sign + delta.toFixed(1) + '%';
      default:                  return sign + delta.toFixed(2);
    }
  }

  formatReason(reason: string): string {
    const map: Record<string, string> = {
      target:        'Target hit',
      stop:          'Stop hit',
      time_stop:     'Time stop',
      gap_skip_up:   'Gap skip ↑',
      gap_skip_down: 'Gap skip ↓',
    };
    return map[reason] ?? reason;
  }

  reasonClass(reason: string): string {
    if (reason === 'target')           return 'reason-target';
    if (reason === 'stop')             return 'reason-stop';
    if (reason === 'time_stop')        return 'reason-time';
    if (reason === 'gap_skip_up' || reason === 'gap_skip_down') return 'reason-gap';
    return '';
  }

  exitReasons(): { reason: string; count: number }[] {
    const er = this.coreMetrics?.exit_reason_breakdown;
    if (!er) return [];
    return Object.entries(er)
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count);
  }

  fmt(v: number | null | undefined): string {
    if (v == null) return '—';
    return (v * 100).toFixed(1) + '%';
  }

  fmtR(v: number | null | undefined): string {
    if (v == null) return '—';
    return (v >= 0 ? '+' : '') + v.toFixed(2) + 'R';
  }

  fmtR3(v: number | null | undefined): string {
    if (v == null) return '—';
    return (v >= 0 ? '+' : '') + v.toFixed(3);
  }

  deltaClass(v: number | null | undefined): string {
    if (v == null) return '';
    if (v > 0.05) return 'positive';
    if (v < -0.05) return 'negative';
    return '';
  }

  // Gate attribution delta: positive delta (near-misses beat qualified) is bad for the gate.
  gateAttribDeltaClass(v: number | null | undefined): string {
    if (v == null) return '';
    if (v > 0.05) return 'negative';   // near-misses outperform → gate blocks good trades
    if (v < -0.05) return 'positive';  // near-misses underperform → gate protects correctly
    return '';
  }

  recClass(rec: string | undefined): string {
    if (rec === 'keep') return 'rec-keep';
    if (rec === 'cut') return 'rec-cut';
    return 'rec-insuff';
  }
}
