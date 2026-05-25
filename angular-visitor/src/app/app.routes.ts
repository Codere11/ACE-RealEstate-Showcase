import { Routes } from '@angular/router';
import { AdminComponent } from './admin/admin.component';
import { OrgDashboardComponent } from './org-dashboard/org-dashboard.component';
import { ReceptionistChatComponent } from './receptionist-chat/receptionist-chat.component';

export const routes: Routes = [
  { path: 'admin', component: AdminComponent },
  { path: 'admin/dashboard', component: AdminComponent },
  { path: ':slug/dashboard', component: OrgDashboardComponent },
  { path: ':slug', component: ReceptionistChatComponent },
  { path: '', component: ReceptionistChatComponent },
  { path: '**', redirectTo: '' },
];
