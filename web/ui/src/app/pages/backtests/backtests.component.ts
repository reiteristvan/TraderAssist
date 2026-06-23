import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService, Run } from '../../services/api.service';

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

  fmt(v: number | null | undefined): string {
    if (v == null) return '—';
    return (v * 100).toFixed(1) + '%';
  }

  fmtR(v: number | null | undefined): string {
    if (v == null) return '—';
    return (v >= 0 ? '+' : '') + v.toFixed(2) + 'R';
  }

  metricKeys(): string[] {
    const m = this.selectedRun?.metrics;
    if (!m) return [];
    return Object.keys(m).filter(k => k !== 'exit_reasons' && k !== 'monthly_signals');
  }

  exitReasons(): { reason: string; count: number }[] {
    const m = this.selectedRun?.metrics as any;
    if (!m?.exit_reasons) return [];
    return Object.entries(m.exit_reasons).map(([reason, count]) => ({ reason, count: count as number }));
  }
}
