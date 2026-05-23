import { Component, inject, signal, computed, output } from '@angular/core';
import { SalonService, TimeSlot } from '../services/salon.service';

@Component({
  selector: 'app-calendar-picker',
  standalone: true,
  templateUrl: './calendar-picker.component.html',
  styleUrls: ['./calendar-picker.component.scss'],
})
export class CalendarPickerComponent {
  readonly salon = inject(SalonService);
  slotSelected = output<string>();
  close = output<void>();

  currentMonth = signal(new Date());
  selectedDate = signal<string | null>(null);
  selectedSlot = signal<string | null>(null);

  readonly dayNames = ['PO', 'TO', 'SR', 'ČE', 'PE', 'SO', 'NE'];
  readonly monthNames = [
    'Januar', 'Februar', 'Marec', 'April', 'Maj', 'Junij',
    'Julij', 'Avgust', 'September', 'Oktober', 'November', 'December',
  ];

  readonly days = computed(() => {
    const date = this.currentMonth();
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    // Adjust for Monday start (getDay: 0=Sun, 1=Mon...)
    let startDow = firstDay.getDay() - 1;
    if (startDow < 0) startDow = 6;

    const cells: (number | null)[] = [];
    for (let i = 0; i < startDow; i++) cells.push(null);
    for (let d = 1; d <= lastDay.getDate(); d++) cells.push(d);

    return cells;
  });

  readonly title = computed(() => {
    const d = this.currentMonth();
    return `${this.monthNames[d.getMonth()]} ${d.getFullYear()}`;
  });

  readonly slots = computed<TimeSlot[]>(() => {
    const date = this.selectedDate();
    if (!date) return [];
    return this.salon.getSlotsForDate(date);
  });

  prevMonth(): void {
    this.currentMonth.update(d => new Date(d.getFullYear(), d.getMonth() - 1, 1));
  }

  nextMonth(): void {
    this.currentMonth.update(d => new Date(d.getFullYear(), d.getMonth() + 1, 1));
  }

  selectDate(day: number | null): void {
    if (day === null) return;
    const y = this.currentMonth().getFullYear();
    const m = this.currentMonth().getMonth();
    const date = `${String(day).padStart(2, '0')}. ${String(m + 1).padStart(2, '0')}. ${y}`;
    this.selectedDate.set(date);
    this.selectedSlot.set(null);
  }

  selectSlot(slot: TimeSlot): void {
    if (!slot.available) return;
    const date = this.selectedDate();
    if (!date) return;
    this.selectedSlot.set(slot.time);
  }

  confirm(): void {
    const date = this.selectedDate();
    const slot = this.selectedSlot();
    if (date && slot) {
      this.slotSelected.emit(`${date} ob ${slot}`);
    }
  }

  formatSlotDate(): string {
    return this.selectedDate() || '';
  }

  padDay(day: number): string {
    return String(day).padStart(2, '0');
  }

  isSelectedDate(day: number): boolean {
    const date = this.selectedDate();
    if (!date) return false;
    return date.startsWith(this.padDay(day));
  }
}
