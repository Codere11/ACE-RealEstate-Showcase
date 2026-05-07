package com.ace.platform.events;

import com.ace.platform.organization.Organization;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class LeadEventService {

    private final LeadEventRepository leadEventRepository;
    private final ObjectMapper objectMapper;

    public LeadEventService(LeadEventRepository leadEventRepository, ObjectMapper objectMapper) {
        this.leadEventRepository = leadEventRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public LeadEvent publish(Organization organization, String sid, String eventType, Map<String, Object> payload) {
        try {
            String json = objectMapper.writeValueAsString(payload != null ? payload : Map.of());
            return leadEventRepository.save(new LeadEvent(organization, sid, eventType, json));
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to serialize lead event payload", ex);
        }
    }

    @Transactional(readOnly = true)
    public List<Map<String, Object>> poll(Long organizationId, String sid, long since, double timeoutSeconds, int limit) {
        long deadline = System.currentTimeMillis() + Math.max(0L, (long) (timeoutSeconds * 1000));
        List<LeadEvent> items = fetch(organizationId, sid, since, limit);
        while (items.isEmpty() && System.currentTimeMillis() < deadline) {
            try {
                Thread.sleep(200L);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                break;
            }
            items = fetch(organizationId, sid, since, limit);
        }
        return items.stream().map(this::toEnvelope).toList();
    }

    private List<LeadEvent> fetch(Long organizationId, String sid, long since, int limit) {
        PageRequest page = PageRequest.of(0, Math.max(1, Math.min(limit, 500)));
        if ("*".equals(sid)) {
            return leadEventRepository.findByOrganizationIdAndIdGreaterThanOrderByIdAsc(organizationId, since, page);
        }
        return leadEventRepository.findByOrganizationIdAndSidAndIdGreaterThanOrderByIdAsc(organizationId, sid, since, page);
    }

    private Map<String, Object> toEnvelope(LeadEvent event) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("type", event.getEventType());
        out.put("sid", event.getSid());
        out.put("ts", event.getCreatedAt() != null ? event.getCreatedAt().toEpochMilli() : Instant.now().toEpochMilli());
        out.put("payload", readPayload(event.getPayloadJson()));
        out.put("_seq", event.getId());
        return out;
    }

    private Map<String, Object> readPayload(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception ex) {
            return Map.of("raw", json);
        }
    }
}
