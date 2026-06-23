import { Pipe, PipeTransform } from '@angular/core';
import { GateSection } from '../pages/diagnosis/diagnosis.component';

@Pipe({ name: 'gatePassCount' })
export class GatePassCountPipe implements PipeTransform {
  transform(sections: GateSection[]): number {
    return sections.flatMap(s => s.entries)
      .filter(e => e.status === 'pass' || e.status === 'bonus_pass').length;
  }
}
