import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService, Signal, GateEntry } from '../../services/api.service';

export interface GateSection {
  title: string;
  entries: GateEntry[];
}

@Component({
  selector: 'app-diagnosis',
  templateUrl: './diagnosis.component.html',
  styleUrls: ['./diagnosis.component.css']
})
export class DiagnosisComponent implements OnInit {
  signal: Signal | null = null;
  sections: GateSection[] = [];
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
      if (s?.gate_detail) this.sections = this._buildSections(s.gate_detail);
      this.loading = false;
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
