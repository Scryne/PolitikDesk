-- -----------------------------------------------------------------------------
-- 0022: scheduled_events linked_event_id foreign key ON DELETE SET NULL
-- -----------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'scheduled_events_linked_event_id_fkey'
          AND table_name = 'scheduled_events'
    ) THEN
        ALTER TABLE scheduled_events DROP CONSTRAINT scheduled_events_linked_event_id_fkey;
    END IF;
END $$;

ALTER TABLE scheduled_events
    ADD CONSTRAINT scheduled_events_linked_event_id_fkey
    FOREIGN KEY (linked_event_id) REFERENCES events(id) ON DELETE SET NULL;
