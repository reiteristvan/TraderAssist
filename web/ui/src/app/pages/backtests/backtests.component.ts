import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService, Run, CoreMetrics, ScoreBucket, ConfBucket, GateAttrib, TradeRecord, FailureAnalysis, TargetBucket } from '../../services/api.service';

@Component({
  selector: 'app-backtests',
  templateUrl: './backtests.component.html',
  styleUrls: ['./backtests.component.css']
})
export class BacktestsComponent implements OnInit {
  runs: Run[] = [];
  selectedRun: Run | null = null;
  loading = true;
  detailLoading = false;

  constructor(
    private api: ApiService,
    private route: ActivatedRoute,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.api.getRuns('backtest').subscribe(r => {
      this.runs = r?.runs ?? [];
      this.loading = false;
      const runId = this.route.snapshot.paramMap.get('run_id');
      if (runId) this.selectRun(runId);
    });
  }

  selectRun(runId: string): void {
    this.detailLoading = true;
    this.router.navigate(['/backtests', runId]);
    this.api.getRun(runId).subscribe(r => {
      this.selectedRun = r;
      this.detailLoading = false;
    });
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
}
