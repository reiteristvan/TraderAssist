import { Component, OnInit } from '@angular/core';
import { ApiService, Run, JournalCompare } from '../../services/api.service';

@Component({
  selector: 'app-calibration',
  templateUrl: './calibration.component.html',
  styleUrls: ['./calibration.component.css']
})
export class CalibrationComponent implements OnInit {
  runs: Run[] = [];
  selectedRunId = '';
  compare: JournalCompare | null = null;
  loading = false;
  runsLoading = true;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.getRuns('backtest').subscribe(r => {
      this.runs = r?.runs ?? [];
      this.runsLoading = false;
    });
  }

  loadCompare(): void {
    if (!this.selectedRunId) return;
    this.loading = true;
    this.compare = null;
    this.api.getJournalCompare(this.selectedRunId).subscribe(c => {
      this.compare = c;
      this.loading = false;
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
}
