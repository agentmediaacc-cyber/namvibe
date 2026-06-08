-- Phase 38: Add voice_duration_seconds to chain_messages
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'chain_messages' AND column_name = 'voice_duration_seconds'
  ) THEN
    ALTER TABLE chain_messages ADD COLUMN voice_duration_seconds INTEGER DEFAULT NULL;
  END IF;
END $$;
