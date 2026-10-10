export type User = { username: string; isAdmin: boolean };
export type Session = { user: User | null; csrfToken: string };
export type Photo = {
  id: string;
  filename: string;
  date: string;
  dateSource: string;
  caption: string;
  width: number;
  height: number;
  camera: string;
  latitude: string | null;
  longitude: string | null;
  thumbnail: string;
  preview: string;
  original: string;
};
export type Page = { photos: Photo[]; next: string | null };
export type Job = { id: string; filename: string; status: string; message: string };
export type Transfer = {
  id: string;
  file: File;
  progress: number;
  state: 'queued' | 'sending' | 'accepted' | 'error';
  error?: string;
};
