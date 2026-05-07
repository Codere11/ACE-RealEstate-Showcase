package com.ace.platform.conversation;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ConversationMessageRepository extends JpaRepository<ConversationMessage, Long> {
    List<ConversationMessage> findByLeadIdOrderByCreatedAtAscIdAsc(Long leadId);
    long countByLeadIdAndRole(Long leadId, ConversationRole role);
}
