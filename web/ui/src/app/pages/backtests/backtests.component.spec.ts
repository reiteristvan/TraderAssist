import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { BacktestsComponent } from './backtests.component';

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
});
