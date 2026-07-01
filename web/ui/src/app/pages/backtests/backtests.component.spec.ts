import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { BacktestsComponent } from './backtests.component';
import { WlAnalysis } from '../../services/api.service';

describe('BacktestsComponent', () => {
  let component: BacktestsComponent;
  let fixture: ComponentFixture<BacktestsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule],
      declarations: [BacktestsComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(BacktestsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('wlAnalysis getter', () => {
    it('returns null when selectedRun is null', () => {
      component.selectedRun = null;
      expect(component.wlAnalysis).toBeNull();
    });

    it('returns null when selectedRun has no wl_analysis', () => {
      component.selectedRun = {
        run_id: 'test-run',
        kind: 'backtest',
        strategy: 'pullback',
        universe: null,
        started_at: null,
        finished_at: null,
        signal_count: null,
      };
      expect(component.wlAnalysis).toBeNull();
    });

    it('returns wl_analysis when populated', () => {
      const wl: WlAnalysis = {
        total_qualified: 342,
        aborted: false,
        abort_reason: null,
        strategies: [],
      };
      component.selectedRun = {
        run_id: 'test-run',
        kind: 'backtest',
        strategy: 'pullback',
        universe: null,
        started_at: null,
        finished_at: null,
        signal_count: null,
        wl_analysis: wl,
      };
      expect(component.wlAnalysis).toEqual(wl);
    });
  });

  describe('fmtWlValue', () => {
    it('returns em dash for null', () => {
      expect(component.fmtWlValue('RSI at entry', null)).toBe('—');
    });

    it('formats RSI at entry to 1 decimal', () => {
      expect(component.fmtWlValue('RSI at entry', 52.3)).toBe('52.3');
    });

    it('formats RVOL with x suffix', () => {
      expect(component.fmtWlValue('RVOL', 1.45)).toBe('1.45x');
    });

    it('formats Pullback depth % with leading sign', () => {
      expect(component.fmtWlValue('Pullback depth %', -8.2)).toBe('-8.2%');
      expect(component.fmtWlValue('Pullback depth %', 3.1)).toBe('+3.1%');
    });

    it('formats ATR multiple to 2 decimals', () => {
      expect(component.fmtWlValue('ATR multiple', 1.20)).toBe('1.20');
    });

    it('formats Industry momentum with leading sign', () => {
      expect(component.fmtWlValue('Industry momentum', 3.4)).toBe('+3.4%');
      expect(component.fmtWlValue('Industry momentum', -0.8)).toBe('-0.8%');
    });

    it('formats Pct to 52w high with % suffix (no forced sign)', () => {
      expect(component.fmtWlValue('Pct to 52w high', 18.3)).toBe('18.3%');
    });
  });

  describe('fmtWlDelta', () => {
    it('returns em dash for null', () => {
      expect(component.fmtWlDelta('RSI at entry', null)).toBe('—');
    });

    it('prepends + for non-negative RSI at entry delta', () => {
      expect(component.fmtWlDelta('RSI at entry', 3.6)).toBe('+3.6');
    });

    it('prepends - for negative RSI at entry delta', () => {
      expect(component.fmtWlDelta('RSI at entry', -2.1)).toBe('-2.1');
    });

    it('formats RVOL delta to 2 decimals with sign', () => {
      expect(component.fmtWlDelta('RVOL', 0.23)).toBe('+0.23');
    });

    it('formats Pullback depth % delta with sign and % suffix', () => {
      expect(component.fmtWlDelta('Pullback depth %', 1.9)).toBe('+1.9%');
    });

    it('formats ATR multiple delta with sign', () => {
      expect(component.fmtWlDelta('ATR multiple', -0.25)).toBe('-0.25');
    });

    it('formats Industry momentum delta with sign and % suffix', () => {
      expect(component.fmtWlDelta('Industry momentum', 4.2)).toBe('+4.2%');
    });

    it('formats Pct to 52w high delta with sign and % suffix', () => {
      expect(component.fmtWlDelta('Pct to 52w high', -4.4)).toBe('-4.4%');
    });

    it('formats positive zero with + sign', () => {
      expect(component.fmtWlDelta('RSI at entry', 0)).toBe('+0.0');
    });
  });
});
