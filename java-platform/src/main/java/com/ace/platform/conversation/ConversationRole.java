package com.ace.platform.conversation;

public enum ConversationRole {
    USER,
    ASSISTANT,
    STAFF,
    SYSTEM;

    public String apiValue() {
        return name().toLowerCase();
    }
}
