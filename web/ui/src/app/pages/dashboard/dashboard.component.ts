import { Component, OnInit } from '@angular/core';
import { ApiService, SummaryStats, Signal } from '../../services/api.service';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
  stats: SummaryStats | null = null;
  topSignals: Signal[] = [];
  loading = true;
  error = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.getSummary().subscribe(s => {
      this.stats = s;
      if (s === null) this.error = true;
    });
    this.api.getLatestSignals({ min_score: 0 }).subscribe(r => {
      this.topSignals = r?.signals.slice(0, 5) ?? [];
      this.loading = false;
    });
  }

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    return iso.slice(0, 16).replace('T', ' ');
  }
}
