export interface SanitizedReview {
  id: string;
  company_id: string;
  platform: string | null;
  author_hash: string | null;
  author_display: string | null;
  text: string;
  rating: number;
  published_at: string | null;
}
