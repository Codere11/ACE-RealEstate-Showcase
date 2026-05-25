import { Component, inject, ElementRef, AfterViewChecked, ViewChild, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SalonService, ChatMessage } from '../services/salon.service';
import { CalendarPickerComponent } from '../calendar-picker/calendar-picker.component';
import { HeaderComponent } from '../header/header.component';
import { ServiceCardsComponent } from '../service-cards/service-cards.component';

@Component({
  selector: 'app-receptionist-chat',
  standalone: true,
  imports: [FormsModule, CalendarPickerComponent, HeaderComponent, ServiceCardsComponent],
  templateUrl: './receptionist-chat.component.html',
  styleUrls: ['./receptionist-chat.component.scss'],
})
export class ReceptionistChatComponent implements AfterViewChecked {
  readonly salon = inject(SalonService);
  inputText = '';
  showCalendar = signal(false);
  minimized = signal(false);

  @ViewChild('chatContainer') private chatContainer!: ElementRef;

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    try {
      this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight;
    } catch (_) {}
  }

  send(): void {
    const text = this.inputText.trim();
    if (!text) return;
    this.inputText = '';

    // Un-minimize if minimized
    if (this.minimized()) {
      this.minimized.set(false);
    }

    this.salon.sendMessage(text);
  }

  retryConnection(): void {
    // SalonService constructor calls connect() — re-instantiate by calling connect
    // We trigger a reconnect by reloading the page for simplicity
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
        this.salon.addMessage({
          role: 'ai',
          text: 'Izberite termin, ki vam najbolj ustreza:',
        });
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
    if (msg.role === 'user') return 'row-user';
    return 'row-ai';
  }
}
