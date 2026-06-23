import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService, Run, CoreMetrics, ScoreBucket, ConfBucket, GateAttrib } from '../../services/api.service';

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
