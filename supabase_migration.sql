-- ── 1. Добавляем is_combo в plans ────────────────────────────────────────────
ALTER TABLE plans ADD COLUMN IF NOT EXISTS is_combo BOOLEAN DEFAULT FALSE;

-- ── 2. Таблица связи план ↔ инструменты (для комбо-планов) ───────────────────
CREATE TABLE IF NOT EXISTS plan_tools (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id    UUID NOT NULL REFERENCES plans(id)  ON DELETE CASCADE,
  tool_id    UUID NOT NULL REFERENCES tools(id)  ON DELETE CASCADE,
  UNIQUE(plan_id, tool_id)
);
ALTER TABLE plan_tools ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read plan_tools"  ON plan_tools FOR SELECT USING (true);

-- ── 3. Таблица пробного доступа ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trials (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tool_id         UUID NOT NULL REFERENCES tools(id)      ON DELETE CASCADE,
  responses_used  INTEGER DEFAULT 0,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, tool_id)
);
ALTER TABLE trials ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own trials"   ON trials FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users insert own trials" ON trials FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own trials" ON trials FOR UPDATE USING (auth.uid() = user_id);

-- ── 4. Разрешаем NULL в tool_id для комбо-планов ─────────────────────────────
ALTER TABLE plans ALTER COLUMN tool_id DROP NOT NULL;
