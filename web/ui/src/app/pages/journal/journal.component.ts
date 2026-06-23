import { Component, OnInit } from '@angular/core';
import { ApiService, Signal } from '../../services/api.service';

@Component({
  selector: 'app-journal',
  templateUrl: './journal.component.html',
  styleUrls: ['./journal.component.css']
})
export class JournalComponent implements OnInit {
  signals: Signal[] = [];
  loading = true;
  filterStatus: '' | 'open' | 'resolved' = '';
  filterStrategy = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading = true;
    const f: any = {};
    if (this.filterStatus)   f.status = this.filterStatus;
    if (this.filterStrategy) f.strategy = this.filterStrategy;
    this.api.getSignalHistory(f).subscribe(r => {
      this.signals = r?.signals ?? [];
      this.loading = false;
    });
  }

  rMultiple(s: Signal): string {
    if (s.r_multiple == null) return '—';
    const v = s.r_multiple;
    return (v >= 0 ? '+' : '') + v.toFixed(2) + 'R';
  }

  rClass(s: Signal): string {
    if (s.r_multiple == null) return '';
    return s.r_multiple >= 0 ? 'positive' : 'negative';
  }
}
