import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { FormsModule } from '@angular/forms';
import { RouterTestingModule } from '@angular/router/testing';
import { CandidatesComponent } from './candidates.component';

function makeSignal(overrides: Record<string, unknown> = {}): any {
  return {
    id: 1,
    date: '2026-07-01',
    ticker: 'AAPL',
    strategy: 'pullback',
    source: 'scan',
    run_id: 'run1',
    score: 7,
    confidence: 'HIGH',
    stop: 190,
    target: 210,
    atr: 3,
    qualified: 1,
    failed_gates: '',
    close: 200,
    ath_zone: null,
    gate_detail: [],
    outcome_checked_at: null,
    entry_px: null,
    exit_px: null,
    exit_reason: null,
    r_multiple: null,
    holding_days: null,
    notes: null,
    industry_group: null,
    industry_momentum: null,
    industry_above_50ma: null,
    industry_rank_pct: null,
    ...overrides
  };
}

describe('CandidatesComponent', () => {
  let component: CandidatesComponent;
  let fixture: ComponentFixture<CandidatesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule, FormsModule],
      declarations: [CandidatesComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(CandidatesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('industryMom formatter', () => {
    it('returns +5.2% for positive momentum', () => {
      expect(component.industryMom(makeSignal({ industry_momentum: 5.2 }))).toBe('+5.2%');
    });

    it('returns -3.1% for negative momentum', () => {
      expect(component.industryMom(makeSignal({ industry_momentum: -3.1 }))).toBe('-3.1%');
    });

    it('returns em dash for null momentum', () => {
      expect(component.industryMom(makeSignal({ industry_momentum: null }))).toBe('—');
    });

    it('returns +0.0% for zero momentum', () => {
      expect(component.industryMom(makeSignal({ industry_momentum: 0 }))).toBe('+0.0%');
    });
  });

  describe('industryRank formatter', () => {
    it('returns integer string for non-null rank', () => {
      expect(component.industryRank(makeSignal({ industry_rank_pct: 18 }))).toBe('18');
    });

    it('returns em dash for null rank', () => {
      expect(component.industryRank(makeSignal({ industry_rank_pct: null }))).toBe('—');
    });

    it('rounds fractional rank', () => {
      expect(component.industryRank(makeSignal({ industry_rank_pct: 18.7 }))).toBe('19');
    });
  });

  describe('industry columns render', () => {
    it('renders Industry and Rank% headers in the table', () => {
      component.signals = [
        makeSignal({
          industry_group: 'Semiconductors',
          industry_momentum: 5.2,
          industry_above_50ma: 1,
          industry_rank_pct: 18
        }),
        makeSignal({
          industry_group: null,
          industry_momentum: null,
          industry_above_50ma: null,
          industry_rank_pct: null
        })
      ];
      component.loading = false;
      fixture.detectChanges();
      const text: string = fixture.nativeElement.textContent;
      expect(text).toContain('Industry');
      expect(text).toContain('Rank%');
    });
  });
});
