import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { CandidatesComponent } from './pages/candidates/candidates.component';
import { DiagnosisComponent } from './pages/diagnosis/diagnosis.component';
import { JournalComponent } from './pages/journal/journal.component';
import { BacktestsComponent } from './pages/backtests/backtests.component';
import { CalibrationComponent } from './pages/calibration/calibration.component';
import { GatePassCountPipe } from './shared/gate-pass-count.pipe';

@NgModule({
  declarations: [
    AppComponent,
    DashboardComponent,
    CandidatesComponent,
    DiagnosisComponent,
    JournalComponent,
    BacktestsComponent,
    CalibrationComponent,
    GatePassCountPipe
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
    AppRoutingModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
