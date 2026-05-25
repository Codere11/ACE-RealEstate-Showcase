import { Component, inject, OnDestroy, signal } from '@angular/core';
import { SalonService } from '../services/salon.service';
import { Room, RoomEvent, RemoteParticipant, RemoteTrack, RemoteTrackPublication, Track } from 'livekit-client';

@Component({
  selector: 'app-staff-video',
  standalone: true,
  templateUrl: './staff-video.component.html',
  styleUrls: ['./staff-video.component.scss'],
})
export class StaffVideoComponent implements OnDestroy {
  readonly salon = inject(SalonService);
  live = signal(false);
  connecting = signal(false);
  private room: Room | null = null;
  private checkTimer: any;

  constructor() {
    this.salon.onStaffMessage = () => {
      // When takeover starts, periodically check for live session
      if (!this.checkTimer) {
        this.checkLive();
        this.checkTimer = setInterval(() => this.checkLive(), 3000);
      }
    };
    this.salon.staffState.set = (() => {}) as any; // no-op, we track via takeover events
  }

  async checkLive() {
    if (this.live() || this.connecting()) return;
    const sid = (this.salon as any).sid;
    if (!sid) return;
    try {
      const slug = this.getTenantSlug();
      const r = await fetch(`/api/public/organizations/${slug}/live-session?sid=${sid}`);
      if (!r.ok) return;
      const data = await r.json();
      if (data.status === 'live' && data.token) {
        this.connecting.set(true);
        await this.joinRoom(data.wsUrl, data.token);
        this.live.set(true);
        this.connecting.set(false);
        if (this.checkTimer) { clearInterval(this.checkTimer); this.checkTimer = null; }
      }
    } catch {}
  }

  async joinRoom(wsUrl: string, token: string) {
    this.room = new Room({ adaptiveStream: true, dynacast: true });
    this.room.on(RoomEvent.TrackSubscribed, (_track: RemoteTrack, _pub: RemoteTrackPublication, participant: RemoteParticipant) => {
      if (_track.kind === Track.Kind.Video) {
        const el = document.getElementById('livekit-video') as HTMLVideoElement;
        if (el) _track.attach(el);
      }
    });
    this.room.on(RoomEvent.Disconnected, () => {
      this.live.set(false);
      this.room = null;
    });
    await this.room.connect(wsUrl, token);
  }

  ngOnDestroy() {
    if (this.checkTimer) clearInterval(this.checkTimer);
    this.room?.disconnect();
  }

  private getTenantSlug(): string {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('org'); if (p) return p;
      const seg = window.location.pathname.replace(/^\/+/, '').split('/')[0]; if (seg) return seg;
    }
    return 'demo';
  }
}
