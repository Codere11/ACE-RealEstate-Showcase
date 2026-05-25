import { Component, inject, signal, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdminService } from '../services/admin.service';
import { firstValueFrom } from 'rxjs';

@Component({
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.scss',
})
export class AdminComponent implements OnInit {
  private api = inject(AdminService);
  orgs = signal<any[]>([]);
  users = signal<any[]>([]);
  error = signal('');

  newOrgName = ''; newOrgSlug = '';
  newUsername = ''; newEmail = ''; newPassword = ''; newRole = 'ORG_USER';

  async ngOnInit() {
    try {
      const [o, u] = await Promise.all([firstValueFrom(this.api.getOrgs()), firstValueFrom(this.api.getUsers())]);
      this.orgs.set(o); this.users.set(u);
    } catch(e: any) { this.error.set((e?.status === 401 ? 'Prijava je potekla.' : 'Napaka: ' + (e?.message || 'neznano')) + ' <a href="/login">Prijavite se</a>.'); }
  }

  async addOrg() {
    if (!this.newOrgName || !this.newOrgSlug) return;
    try {
      await firstValueFrom(this.api.createOrg(this.newOrgName, this.newOrgSlug));
      this.newOrgName = ''; this.newOrgSlug = '';
      this.orgs.set(await firstValueFrom(this.api.getOrgs()));
    } catch (e: any) { this.error.set(e.error?.detail || 'Napaka pri ustvarjanju.'); }
  }

  async addUser() {
    if (!this.newUsername || !this.newEmail || !this.newPassword) return;
    try {
      await firstValueFrom(this.api.createUser(this.newUsername, this.newEmail, this.newPassword, this.newRole));
      this.newUsername = ''; this.newEmail = ''; this.newPassword = '';
      this.users.set(await firstValueFrom(this.api.getUsers()));
    } catch (e: any) { this.error.set(e.error?.detail || 'Napaka pri ustvarjanju.'); }
  }
}
