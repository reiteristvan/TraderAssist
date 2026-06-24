import { Component, OnInit } from '@angular/core';
import { ApiService, Signal } from '../../services/api.service';

interface CloseForm {
  exit_reason: string;
  entry_px: string;
  exit_px: string;
  notes: string;
}

interface DismissForm {
  notes: string;
}

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

  activeId: number | null = null;
  formMode: 'close' | 'dismiss' | null = null;
  savingId: number | null = null;

  closeForm: CloseForm = { exit_reason: 'target', entry_px: '', exit_px: '', notes: '' };
  dismissForm: DismissForm = { notes: '' };

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

  openDismissForm(s: Signal): void {
    this.activeId = s.id;
    this.formMode = 'dismiss';
    this.dismissForm = { notes: '' };
  }

  openCloseForm(s: Signal): void {
    this.activeId = s.id;
    this.formMode = 'close';
    this.closeForm = { exit_reason: 'target', entry_px: '', exit_px: '', notes: '' };
  }

  cancelForm(): void {
    this.activeId = null;
    this.formMode = null;
  }

  submitDismiss(s: Signal): void {
    this.savingId = s.id;
    this.api.updateSignal(s.id, {
      exit_reason: 'dismissed',
      notes: this.dismissForm.notes.trim() || null,
    }).subscribe({
      next: () => { this.savingId = null; this.activeId = null; this.formMode = null; this.load(); },
      error: () => { this.savingId = null; },
    });
  }

  submitClose(s: Signal): void {
    const body: Parameters<ApiService['updateSignal']>[1] = {
      exit_reason: this.closeForm.exit_reason,
      notes: this.closeForm.notes.trim() || null,
    };
    const ep = parseFloat(this.closeForm.entry_px);
    const xp = parseFloat(this.closeForm.exit_px);
    if (!isNaN(ep)) body.entry_px = ep;
    if (!isNaN(xp)) body.exit_px = xp;
    if (!isNaN(ep) && !isNaN(xp) && s.stop != null) {
      const denom = ep - s.stop;
      if (denom > 0) {
        body.r_multiple = Math.round(((xp - ep) / denom) * 1000) / 1000;
      }
    }
    this.savingId = s.id;
    this.api.updateSignal(s.id, body).subscribe({
      next: () => { this.savingId = null; this.activeId = null; this.formMode = null; this.load(); },
      error: () => { this.savingId = null; },
    });
  }

  isSaving(s: Signal): boolean { return this.savingId === s.id; }

  rMultiple(s: Signal): string {
    if (s.r_multiple == null) return '—';
    const v = s.r_multiple;
    return (v >= 0 ? '+' : '') + v.toFixed(2) + 'R';
  }

  rClass(s: Signal): string {
    if (s.r_multiple == null) return '';
    return s.r_multiple >= 0 ? 'positive' : 'negative';
  }

  exitLabel(s: Signal): string {
    if (s.exit_reason === null) return '—';
    const map: Record<string, string> = {
      target:    'Target hit',
      stop:      'Stop hit',
      time_stop: 'Time stop',
      manual:    'Manual close',
      dismissed: 'Dismissed',
    };
    return map[s.exit_reason] ?? s.exit_reason;
  }

  statusLabel(s: Signal): string {
    if (s.exit_reason === null) return 'Open';
    if (s.exit_reason === 'dismissed') return 'Dismissed';
    return 'Closed';
  }

  statusClass(s: Signal): string {
    if (s.exit_reason === null) return 'badge-pass';
    if (s.exit_reason === 'dismissed') return 'badge-dim';
    return 'badge-medium';
  }

  computedR(s: Signal): string | null {
    const ep = parseFloat(this.closeForm.entry_px);
    const xp = parseFloat(this.closeForm.exit_px);
    if (isNaN(ep) || isNaN(xp) || s.stop == null) return null;
    const denom = ep - s.stop;
    if (denom <= 0) return null;
    return ((xp - ep) / denom).toFixed(2);
  }
}
