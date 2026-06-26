import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

export interface GateEntry {
  name: string;
  status: 'pass' | 'fail' | 'skip' | 'bonus_pass' | 'bonus_fail' | 'section';
  detail: string;
}

export interface Signal {
  id: number;
  date: string;
  ticker: string;
  strategy: string;
  source: string;
  run_id: string;
  score: number;
  confidence: string | null;
  stop: number | null;
  target: number | null;
  atr: number | null;
  qualified: number;
  failed_gates: string;
  close: number | null;
  ath_zone: string | null;
  gate_detail: GateEntry[];
  outcome_checked_at: string | null;
  entry_px: number | null;
  exit_px: number | null;
  exit_reason: string | null;
  r_multiple: number | null;
  holding_days: number | null;
  notes: string | null;
}

export interface CoreMetrics {
  count: number;
  win_rate: number | null;
  avg_win_r: number | null;
  avg_loss_r: number | null;
  expectancy_r: number | null;
  median_holding_days: number | null;
  max_drawdown_r: number | null;
  exit_reason_breakdown: Record<string, number>;
  ambiguous_bar_pct: number;
  gap_skip_pct: number;
  incomplete_pct: number;
}

export interface ScoreBucket {
  bucket: string;
  n: number;
  win_rate: number | null;
  expectancy_r: number | null;
  verdict: string;
}

export interface ConfBucket {
  bucket: string;
  n: number;
  win_rate: number | null;
  expectancy_r: number | null;
  verdict: string;
}

export interface TradeRecord {
  ticker: string;
  signal_date: string;
  entry_date: string | null;
  exit_date: string | null;
  exit_reason: string;
  stop: number | null;
  target: number | null;
  entry_px: number | null;
  exit_px: number | null;
  r_multiple: number | null;
  holding_days: number | null;
  strategy: string;
  confidence: string | null;
  score: number;
}

export interface GateAttrib {
  gate: string;
  n: number;
  expectancy_r: number | null;
  qualified_expectancy_r: number | null;
  delta_r: number | null;
  verdict: string;
}

export interface Run {
  run_id: string;
  kind: 'scan' | 'backtest';
  strategy: string | null;
  universe: string | null;
  started_at: string | null;
  finished_at: string | null;
  signal_count: number | null;
  metrics?: CoreMetrics | null;
  score_buckets?: ScoreBucket[] | null;
  conf_buckets?: ConfBucket[] | null;
  gate_attribution?: GateAttrib[] | null;
  monthly_signals?: Record<string, number> | null;
  biases?: string[] | null;
  trades?: TradeRecord[] | null;
}

export interface SummaryStats {
  open_positions: number;
  signals_tonight: number;
  last_scan_run: {
    run_id: string;
    started_at: string;
    finished_at: string | null;
    signal_count: number;
    strategy: string | null;
  } | null;
}

export interface JournalCompare {
  live_n: number;
  live_expectancy_r: number | null;
  live_win_rate: number | null;
  backtest_run_id: string;
  backtest_n: number | null;
  backtest_expectancy_r: number | null;
  backtest_win_rate: number | null;
  warning: string | null;
}

export interface OhlcvBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Job {
  id: number;
  kind: string;
  params: Record<string, unknown>;
  status: 'queued' | 'running' | 'done' | 'error';
  result_ref: string | null;
  created_at: string;
  finished_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = '/api';

  constructor(private http: HttpClient) {}

  getSummary(): Observable<SummaryStats | null> {
    return this.http.get<SummaryStats>(`${this.base}/stats/summary`).pipe(
      catchError(() => of(null))
    );
  }

  getLatestSignals(filters: { strategy?: string; min_score?: number; confidence?: string } = {}):
      Observable<{ count: number; signals: Signal[] } | null> {
    let params = new HttpParams();
    if (filters.strategy)       params = params.set('strategy',  filters.strategy);
    if (filters.min_score != null) params = params.set('min_score', String(filters.min_score));
    if (filters.confidence)     params = params.set('confidence', filters.confidence);
    return this.http.get<{ count: number; signals: Signal[] }>(`${this.base}/signals/latest`, { params }).pipe(
      catchError(() => of(null))
    );
  }

  getSignal(id: number): Observable<Signal | null> {
    return this.http.get<Signal>(`${this.base}/signals/${id}`).pipe(
      catchError(() => of(null))
    );
  }

  getSignalHistory(filters: { from?: string; to?: string; status?: 'open' | 'resolved'; strategy?: string } = {}):
      Observable<{ count: number; signals: Signal[] } | null> {
    let params = new HttpParams();
    if (filters.from)     params = params.set('from',     filters.from);
    if (filters.to)       params = params.set('to',       filters.to);
    if (filters.status)   params = params.set('status',   filters.status);
    if (filters.strategy) params = params.set('strategy', filters.strategy);
    return this.http.get<{ count: number; signals: Signal[] }>(`${this.base}/signals/history`, { params }).pipe(
      catchError(() => of(null))
    );
  }

  getRuns(kind?: 'scan' | 'backtest'): Observable<{ count: number; runs: Run[] } | null> {
    let params = new HttpParams();
    if (kind) params = params.set('kind', kind);
    return this.http.get<{ count: number; runs: Run[] }>(`${this.base}/runs`, { params }).pipe(
      catchError(() => of(null))
    );
  }

  getRun(runId: string): Observable<Run | null> {
    return this.http.get<Run>(`${this.base}/runs/${encodeURIComponent(runId)}`).pipe(
      catchError(() => of(null))
    );
  }

  getJournalCompare(backtestRunId: string): Observable<JournalCompare | null> {
    const params = new HttpParams().set('backtest_run', backtestRunId);
    return this.http.get<JournalCompare>(`${this.base}/journal/compare`, { params }).pipe(
      catchError(() => of(null))
    );
  }

  updateSignal(id: number, data: {
    exit_reason: string;
    entry_px?: number | null;
    exit_px?: number | null;
    r_multiple?: number | null;
    holding_days?: number | null;
    notes?: string | null;
  }): Observable<Signal | null> {
    return this.http.patch<Signal>(`${this.base}/signals/${id}`, data).pipe(
      catchError(() => of(null))
    );
  }

  postJob(kind: string, params: Record<string, unknown>): Observable<{ id: number; status: string } | null> {
    return this.http.post<{ id: number; status: string }>(`${this.base}/jobs`, { kind, params }).pipe(
      catchError(() => of(null))
    );
  }

  pollJob(id: number): Observable<Job | null> {
    return this.http.get<Job>(`${this.base}/jobs/${id}`).pipe(
      catchError(() => of(null))
    );
  }

  getOhlcv(ticker: string, bars = 120):
      Observable<{ ticker: string; count: number; bars: OhlcvBar[] } | null> {
    const params = new HttpParams().set('bars', String(bars));
    return this.http.get<{ ticker: string; count: number; bars: OhlcvBar[] }>(
      `${this.base}/ohlcv/${encodeURIComponent(ticker)}`, { params }
    ).pipe(catchError(() => of(null)));
  }
}
