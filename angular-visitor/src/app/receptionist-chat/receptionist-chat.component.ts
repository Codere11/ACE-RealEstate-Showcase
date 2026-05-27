import { Component, inject, ElementRef, AfterViewChecked, ViewChild, signal, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SalonService, ChatMessage } from '../services/salon.service';
import { CalendarPickerComponent } from '../calendar-picker/calendar-picker.component';
import { HeaderComponent } from '../header/header.component';
import { ServiceCardsComponent } from '../service-cards/service-cards.component';
import { StaffVideoComponent } from '../staff-video/staff-video.component';

@Component({
  selector: 'app-receptionist-chat',
  standalone: true,
  imports: [FormsModule, CalendarPickerComponent, HeaderComponent, ServiceCardsComponent, StaffVideoComponent],
  templateUrl: './receptionist-chat.component.html',
  styleUrls: ['./receptionist-chat.component.scss'],
})
export class ReceptionistChatComponent implements AfterViewChecked {
  readonly salon = inject(SalonService);
  private cdr = inject(ChangeDetectorRef);
  inputText = '';
  private prevLen = 0;
  unreadCount = signal(0);

  constructor() {
    this.salon.onStaffMessage = () => this.cdr.detectChanges();
  }
  showCalendar = signal(false);
  minimized = signal(false);

  @ViewChild('chatContainer') private chatContainer!: ElementRef;

  ngAfterViewChecked(): void {
    const el = this.chatContainer?.nativeElement;
    if (!el) return;
    const currentLen = this.salon.messages().length;
    if (currentLen !== this.prevLen) {
      const newMsgs = currentLen - this.prevLen;
      this.prevLen = currentLen;
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
      if (atBottom) {
        el.scrollTop = el.scrollHeight;
        this.unreadCount.set(0);
      } else {
        this.unreadCount.update(c => c + Math.max(0, newMsgs));
      }
    }
  }

  scrollToBottom(): void {
    const el = this.chatContainer?.nativeElement;
    if (el) { el.scrollTop = el.scrollHeight; this.unreadCount.set(0); }
  }

  onScroll(): void {
    const el = this.chatContainer?.nativeElement;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 50) {
      this.unreadCount.set(0);
    }
  }

  send(): void {
    const text = this.inputText.trim();
    if (!text) return;
    this.inputText = '';
    if (this.minimized()) this.minimized.set(false);
    this.salon.sendMessage(text);
  }

  retryConnection(): void {
    window.location.reload();
  }

  toggleMinimize(): void {
    this.minimized.update(v => !v);
  }

  onAction(actionType: string): void {
    switch (actionType) {
      case 'request-staff':
        this.salon.requestStaff();
        break;
      case 'book-appointment':
        this.showCalendar.set(true);
        this.salon.addMessage({ role: 'ai', text: 'Izberite termin, ki vam najbolj ustreza:' });
        break;
      case 'accept-staff':
        this.salon.acceptStaff();
        break;
      case 'deny-staff':
        this.salon.denyStaff();
        break;
    }
  }

  onSlotSelected(slot: string): void {
    this.showCalendar.set(false);
    const service = this.salon.selectedService();
    if (service && slot) {
      this.salon.addMessage({
        role: 'ai',
        text: `Super! Vaš termin je potrjen:\n\n📅 ${slot}\n💆‍♀️ ${service.name} (${service.durationMin} min)\n💶 ${service.priceEur} €\n\nVas lahko še s čim drugim pomagam? ☺️`,
      });
    }
  }

  onCalendarClose(): void {
    this.showCalendar.set(false);
  }

  messageClass(msg: ChatMessage): string {
    if (msg.role === 'system') return 'message-system';
    if (msg.role === 'staff') return 'message-staff';
    return msg.role === 'ai' ? 'message-ai' : 'message-user';
  }

  avatarFor(msg: ChatMessage): string {
    if (msg.role === 'staff') return '👩‍💼';
    if (msg.role === 'system') return '🔔';
    return '🤖';
  }

  rowClass(msg: ChatMessage): string {
    return msg.role === 'user' ? 'row-user' : 'row-ai';
  }
}
