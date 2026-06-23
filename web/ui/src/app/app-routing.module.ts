import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { DashboardComponent }   from './pages/dashboard/dashboard.component';
import { CandidatesComponent }  from './pages/candidates/candidates.component';
import { DiagnosisComponent }   from './pages/diagnosis/diagnosis.component';
import { JournalComponent }     from './pages/journal/journal.component';
import { BacktestsComponent }   from './pages/backtests/backtests.component';
import { CalibrationComponent } from './pages/calibration/calibration.component';

const routes: Routes = [
  { path: '',              redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard',    component: DashboardComponent },
  { path: 'candidates',   component: CandidatesComponent },
  { path: 'diagnosis/:id', component: DiagnosisComponent },
  { path: 'journal',      component: JournalComponent },
  { path: 'backtests',    component: BacktestsComponent },
  { path: 'backtests/:run_id', component: BacktestsComponent },
  { path: 'calibration',  component: CalibrationComponent },
  { path: '**',           redirectTo: 'dashboard' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
