import { Component } from '@angular/core';
import { HeaderComponent } from './header/header.component';
import { ServiceCardsComponent } from './service-cards/service-cards.component';
import { ReceptionistChatComponent } from './receptionist-chat/receptionist-chat.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [HeaderComponent, ServiceCardsComponent, ReceptionistChatComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent {}
