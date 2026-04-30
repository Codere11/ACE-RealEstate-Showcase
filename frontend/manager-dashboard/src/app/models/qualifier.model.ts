export interface Qualifier {
  id: number;
  organization_id: number;
  name: string;
  slug: string;
  status: 'draft' | 'live' | 'archived';
  system_prompt: string;
  assistant_style: string;
  goal_definition: string;
  field_schema?: any;
  required_fields?: string[];
  scoring_rules?: any;
  band_thresholds?: any;
  confidence_thresholds?: any;
  takeover_rules?: any;
  video_offer_rules?: any;
  rag_enabled: boolean;
  knowledge_source_ids?: any[];
  max_clarifying_questions: number;
  contact_capture_policy: string;
  version: number;
  version_notes: string;
  created_at: string;
  updated_at: string;
  published_at?: string | null;
}

export interface QualifierCreate {
  organization_id: number;
  name: string;
  slug: string;
  status: 'draft' | 'live' | 'archived';
  system_prompt: string;
  assistant_style: string;
  goal_definition: string;
  field_schema?: any;
  required_fields?: string[];
  scoring_rules?: any;
  band_thresholds?: any;
  confidence_thresholds?: any;
  takeover_rules?: any;
  video_offer_rules?: any;
  rag_enabled: boolean;
  knowledge_source_ids?: any[];
  max_clarifying_questions: number;
  contact_capture_policy: string;
  version: number;
  version_notes: string;
}

export interface QualifierUpdate {
  name?: string;
  slug?: string;
  status?: 'draft' | 'live' | 'archived';
  system_prompt?: string;
  assistant_style?: string;
  goal_definition?: string;
  field_schema?: any;
  required_fields?: string[];
  scoring_rules?: any;
  band_thresholds?: any;
  confidence_thresholds?: any;
  takeover_rules?: any;
  video_offer_rules?: any;
  rag_enabled?: boolean;
  knowledge_source_ids?: any[];
  max_clarifying_questions?: number;
  contact_capture_policy?: string;
  version?: number;
  version_notes?: string;
}
