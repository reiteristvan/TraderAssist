import { Component, OnInit } from '@angular/core';
import { ApiService, Signal } from '../../services/api.service';

@Component({
  selector: 'app-candidates',
  templateUrl: './candidates.component.html',
  styleUrls: ['./candidates.component.css']
})
export class CandidatesComponent implements OnInit {
  signals: Signal[] = [];
  loading = true;
  filterStrategy = '';
  filterConfidence = '';
  filterMinScore: number | null = null;
  sortCol = 'score';
  sortAsc = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading = true;
    const f: any = {};
    if (this.filterStrategy)   f.strategy = this.filterStrategy;
    if (this.filterConfidence) f.confidence = this.filterConfidence;
    if (this.filterMinScore != null) f.min_score = this.filterMinScore;
    this.api.getLatestSignals(f).subscribe(r => {
      this.signals = r?.signals ?? [];
      this.loading = false;
    });
  }

  sort(col: string): void {
    if (this.sortCol === col) { this.sortAsc = !this.sortAsc; }
    else { this.sortCol = col; this.sortAsc = false; }
  }

  get sorted(): Signal[] {
    const dir = this.sortAsc ? 1 : -1;
    return [...this.signals].sort((a, b) => {
      const av = (a as any)[this.sortCol] ?? 0;
      const bv = (b as any)[this.sortCol] ?? 0;
      return av < bv ? -dir : av > bv ? dir : 0;
    });
  }

  rr(s: Signal): string {
    if (s.stop == null || s.target == null || s.close == null) return '—';
    const r = (s.target - s.close) / (s.close - s.stop);
    return isFinite(r) ? r.toFixed(2) + 'R' : '—';
  }
}
