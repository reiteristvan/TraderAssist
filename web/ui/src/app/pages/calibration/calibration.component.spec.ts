import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { FormsModule } from '@angular/forms';
import { CalibrationComponent } from './calibration.component';

describe('CalibrationComponent', () => {
  let component: CalibrationComponent;
  let fixture: ComponentFixture<CalibrationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, FormsModule],
      declarations: [CalibrationComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(CalibrationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
