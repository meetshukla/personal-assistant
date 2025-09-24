-- Supabase Database Setup for Personal Assistant
-- Run these SQL commands in your Supabase SQL editor

-- Create conversations table
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    phone_number TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'specialist')),
    content TEXT NOT NULL,
    message_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_conversations_phone_number ON public.conversations(phone_number);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON public.conversations(timestamp);

-- Create reminders table
CREATE TABLE IF NOT EXISTS public.reminders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    phone_number TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    scheduled_time TIMESTAMPTZ NOT NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('one_time', 'recurring')),
    recurrence_pattern TEXT,
    specialist_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_reminders_phone_number ON public.reminders(phone_number);
CREATE INDEX IF NOT EXISTS idx_reminders_scheduled_time ON public.reminders(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_reminders_active ON public.reminders(active);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON public.reminders(scheduled_time, active, completed);

-- Enable Row Level Security (RLS)
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reminders ENABLE ROW LEVEL SECURITY;

-- Create policies for conversations table
-- Allow all operations for now (you can restrict this later based on your auth requirements)
CREATE POLICY "Enable all operations for conversations" ON public.conversations
    FOR ALL USING (true) WITH CHECK (true);

-- Create policies for reminders table
-- Allow all operations for now (you can restrict this later based on your auth requirements)
CREATE POLICY "Enable all operations for reminders" ON public.reminders
    FOR ALL USING (true) WITH CHECK (true);

-- Grant necessary permissions
GRANT ALL ON public.conversations TO anon;
GRANT ALL ON public.reminders TO anon;
GRANT ALL ON public.conversations TO authenticated;
GRANT ALL ON public.reminders TO authenticated;