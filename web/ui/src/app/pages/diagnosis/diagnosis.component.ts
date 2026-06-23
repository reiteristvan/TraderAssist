import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService, Signal, GateEntry } from '../../services/api.service';

@Component({
  selector: 'app-diagnosis',
  templateUrl: './diagnosis.component.html',
  styleUrls: ['./diagnosis.component.css']
})
export class DiagnosisComponent implements OnInit {
  signal: Signal | null = null;
  loading = true;
  notFound = false;

  accountSize = 6500;
  riskPct = 1;

  constructor(private route: ActivatedRoute, private api: ApiService) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (isNaN(id)) { this.notFound = true; this.loading = false; return; }
    this.api.getSignal(id).subscribe(s => {
      this.signal = s;
      this.notFound = s === null;
      this.loading = false;
    });
  }

  get shares(): number {
    const s = this.signal;
    if (!s?.close || !s?.stop) return 0;
    const riskDollars = this.accountSize * (this.riskPct / 100);
    const perShare = s.close - s.stop;
    if (perShare <= 0) return 0;
    const maxShares = Math.floor((this.accountSize * 0.1) / s.close);
    return Math.min(Math.floor(riskDollars / perShare), maxShares);
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

  gateStatusClass(entry: GateEntry): string {
    if (entry.status === 'pass' || entry.status === 'bonus_pass') return 'badge-pass';
    if (entry.status === 'fail' || entry.status === 'bonus_fail') return 'badge-fail';
    return 'badge-skip';
  }

  gateIcon(entry: GateEntry): string {
    if (entry.status === 'pass' || entry.status === 'bonus_pass') return '✓';
    if (entry.status === 'fail' || entry.status === 'bonus_fail') return '✗';
    return '–';
  }
}
