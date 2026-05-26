import { Component, inject, OnDestroy, signal, NgZone } from '@angular/core';
import { SalonService } from '../services/salon.service';
import { Room, RoomEvent, RemoteParticipant, RemoteTrack, RemoteTrackPublication, Track, ConnectionState } from 'livekit-client';

@Component({
  selector: 'app-staff-video',
  standalone: true,
  templateUrl: './staff-video.component.html',
  styleUrls: ['./staff-video.component.scss'],
})
export class StaffVideoComponent implements OnDestroy {
  readonly salon = inject(SalonService);
  private zone = inject(NgZone);
  live = signal(false);
  connecting = signal(false);
  private room: Room | null = null;
  private checkTimer: any = null;
  private retryCount = 0;
  private maxRetries = 5;
  private disposed = false;

  constructor() {
    this.salon.onStaffMessage = () => this.startChecking();

    // Also watch for live_session events directly via staffState
    const originalSet = this.salon.staffState.set.bind(this.salon.staffState);
    this.salon.staffState.set = (value: any) => {
      originalSet(value);
      if (value === 'connected') {
        this.startChecking();
      } else if (value === 'idle') {
        this.stopChecking();
        this.zone.run(() => this.disconnectRoom());
      }
    };
  }

  private startChecking() {
    if (this.disposed || this.checkTimer) return;
    this.checkLive();
    this.checkTimer = setInterval(() => this.checkLive(), 3000);
  }

  private stopChecking() {
    if (this.checkTimer) {
      clearInterval(this.checkTimer);
      this.checkTimer = null;
    }
  }

  async checkLive() {
    if (this.disposed || this.live() || this.connecting()) return;
    const sid = (this.salon as any).sid;
    if (!sid) return;
    try {
      const slug = this.getTenantSlug();
      const r = await fetch(`/api/public/organizations/${slug}/live-session?sid=${sid}`);
      if (!r.ok) return;
      const data = await r.json();
      if (data.status === 'live' && data.token) {
        this.connecting.set(true);
        try {
          await this.joinRoom(data.wsUrl, data.token);
          this.retryCount = 0;
          this.live.set(true);
          this.connecting.set(false);
          this.stopChecking();
        } catch (e) {
          console.warn('LiveKit join failed, retrying...', e);
          this.retryCount++;
          this.connecting.set(false);
          if (this.retryCount >= this.maxRetries) {
            this.stopChecking();
          }
        }
      }
    } catch {}
  }

  async joinRoom(wsUrl: string, token: string) {
    // Clean up any previous room
    this.disconnectRoom();
    await new Promise(r => setTimeout(r, 100));

    this.room = new Room({
      adaptiveStream: true,
      dynacast: true,
    });

    this.room.on(RoomEvent.TrackSubscribed, (_track: RemoteTrack, _pub: RemoteTrackPublication, _participant: RemoteParticipant) => {
      this.zone.run(() => {
        if (_track.kind === Track.Kind.Video) {
          const el = document.getElementById('livekit-video') as HTMLVideoElement;
          if (el) {
            _track.attach(el);
            el.style.opacity = '0';
            // Small delay then fade the video content
            requestAnimationFrame(() => {
              el.style.transition = 'opacity 0.6s ease';
              el.style.opacity = '1';
            });
          }
        }
      });
    });

    this.room.on(RoomEvent.Disconnected, () => {
      this.zone.run(() => {
        // Only clear live state if we weren't the ones disconnecting
        if (!this.disposed) {
          this.live.set(false);
          this.room = null;
          // Try to reconnect
          this.retryCount = 0;
          this.startChecking();
        }
      });
    });

    this.room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
      if (state === ConnectionState.Reconnecting) {
        console.log('LiveKit: reconnecting...');
      }
    });

    await this.room.connect(wsUrl, token);
  }

  private disconnectRoom() {
    try { this.room?.disconnect(); } catch {}
    this.room = null;
    this.live.set(false);
    this.connecting.set(false);
  }

  ngOnDestroy() {
    this.disposed = true;
    this.stopChecking();
    this.disconnectRoom();
  }

  private getTenantSlug(): string {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('org'); if (p) return p;
      const seg = window.location.pathname.replace(/^\/+/, '').split('/')[0]; if (seg) return seg;
    }
    return 'demo';
  }
}
