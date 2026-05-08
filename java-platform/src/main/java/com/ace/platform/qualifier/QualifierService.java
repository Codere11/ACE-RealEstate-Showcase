package com.ace.platform.qualifier;

import com.ace.platform.organization.Organization;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

@Service
public class QualifierService {

    private final QualifierRepository qualifierRepository;

    public QualifierService(QualifierRepository qualifierRepository) {
        this.qualifierRepository = qualifierRepository;
    }

    @Transactional(readOnly = true)
    public List<Qualifier> listForOrganization(Long organizationId) {
        return qualifierRepository.findByOrganizationIdOrderByUpdatedAtDescCreatedAtDesc(organizationId);
    }

    @Transactional(readOnly = true)
    public Qualifier getQualifier(Long organizationId, Long qualifierId) {
        return qualifierRepository.findByIdAndOrganizationId(qualifierId, organizationId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Qualifier not found"));
    }

    @Transactional(readOnly = true)
    public Optional<Qualifier> findActive(Long organizationId) {
        return qualifierRepository.findByOrganizationIdAndStatus(organizationId, "live");
    }

    @Transactional(readOnly = true)
    public Optional<Qualifier> findDefaultSelection(Long organizationId) {
        Optional<Qualifier> active = findActive(organizationId);
        if (active.isPresent()) {
            return active;
        }
        return listForOrganization(organizationId).stream().findFirst();
    }

    @Transactional
    public Qualifier createQualifier(Organization organization, UpsertRequest request) {
        String name = normalizeName(request.name());
        String slug = normalizeSlug(request.slug());
        ensureSlugUnique(organization.getId(), slug, null);

        Qualifier qualifier = new Qualifier(organization, name, slug);
        applyUpsert(qualifier, request, true);
        validateBeforeSave(organization.getId(), qualifier, null, true);
        return qualifierRepository.save(qualifier);
    }

    @Transactional
    public Qualifier updateQualifier(Organization organization, Long qualifierId, UpsertRequest request) {
        Qualifier qualifier = getQualifier(organization.getId(), qualifierId);
        if ("live".equalsIgnoreCase(qualifier.getStatus()) && request.containsRuntimeFields()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Cannot edit a live qualifier. Archive it first.");
        }
        String slug = request.slug() != null ? normalizeSlug(request.slug()) : qualifier.getSlug();
        ensureSlugUnique(organization.getId(), slug, qualifierId);
        applyUpsert(qualifier, request, false);
        qualifier.setSlug(slug);
        validateBeforeSave(organization.getId(), qualifier, qualifierId, false);
        return qualifierRepository.save(qualifier);
    }

    @Transactional
    public Qualifier publish(Organization organization, Long qualifierId) {
        Qualifier qualifier = getQualifier(organization.getId(), qualifierId);
        ensureSingleLive(organization.getId(), qualifierId);
        validatePublishable(qualifier);
        qualifier.setStatus("live");
        qualifier.setPublishedAt(qualifier.getPublishedAt() != null ? qualifier.getPublishedAt() : Instant.now());
        return qualifierRepository.save(qualifier);
    }

    @Transactional
    public Qualifier archive(Organization organization, Long qualifierId) {
        Qualifier qualifier = getQualifier(organization.getId(), qualifierId);
        qualifier.setStatus("archived");
        return qualifierRepository.save(qualifier);
    }

    @Transactional(readOnly = true)
    public PublicActiveQualifierResponse publicActiveQualifier(Organization organization) {
        Qualifier qualifier = findActive(organization.getId()).orElse(null);
        return new PublicActiveQualifierResponse(
            organization.getSlug(),
            qualifier != null,
            qualifier != null ? new PublicQualifierSummary(
                qualifier.getId(),
                qualifier.getSlug(),
                qualifier.getName(),
                qualifier.getAssistantStyle()
            ) : null
        );
    }

    private void applyUpsert(Qualifier qualifier, UpsertRequest request, boolean creating) {
        if (request.name() != null || creating) {
            qualifier.setName(normalizeName(request.name()));
        }
        if (request.slug() != null || creating) {
            qualifier.setSlug(normalizeSlug(request.slug()));
        }
        if (request.status() != null) {
            qualifier.setStatus(normalizeStatus(request.status()));
        } else if (creating && (qualifier.getStatus() == null || qualifier.getStatus().isBlank())) {
            qualifier.setStatus("draft");
        }
        if (request.systemPrompt() != null) {
            qualifier.setSystemPrompt(request.systemPrompt().trim());
        } else if (creating && qualifier.getSystemPrompt() == null) {
            qualifier.setSystemPrompt("");
        }
        if (request.assistantStyle() != null) {
            qualifier.setAssistantStyle(normalizeOptional(request.assistantStyle(), "friendly, concise, consultative"));
        }
        if (request.goalDefinition() != null) {
            qualifier.setGoalDefinition(normalizeOptional(request.goalDefinition(), ""));
        }
        if (request.fieldSchema() != null) {
            qualifier.setFieldSchema(cleanMap(request.fieldSchema()));
        }
        if (request.requiredFields() != null) {
            qualifier.setRequiredFields(cleanStrings(request.requiredFields()));
        }
        if (request.scoringRules() != null) {
            qualifier.setScoringRules(cleanMap(request.scoringRules()));
        }
        if (request.bandThresholds() != null) {
            qualifier.setBandThresholds(cleanMap(request.bandThresholds()));
        }
        if (request.confidenceThresholds() != null) {
            qualifier.setConfidenceThresholds(cleanMap(request.confidenceThresholds()));
        }
        if (request.takeoverRules() != null) {
            qualifier.setTakeoverRules(cleanMap(request.takeoverRules()));
        }
        if (request.videoOfferRules() != null) {
            qualifier.setVideoOfferRules(cleanMap(request.videoOfferRules()));
        }
        if (request.ragEnabled() != null) {
            qualifier.setRagEnabled(request.ragEnabled());
        }
        if (request.knowledgeSourceIds() != null) {
            qualifier.setKnowledgeSourceIds(cleanStrings(request.knowledgeSourceIds()));
        }
        if (request.maxClarifyingQuestions() != null) {
            qualifier.setMaxClarifyingQuestions(Math.max(0, Math.min(request.maxClarifyingQuestions(), 20)));
        }
        if (request.contactCapturePolicy() != null) {
            qualifier.setContactCapturePolicy(normalizeOptional(request.contactCapturePolicy(), "when_high_intent_or_explicit"));
        }
        if (request.version() != null) {
            qualifier.setVersion(Math.max(1, request.version()));
        }
        if (request.versionNotes() != null) {
            qualifier.setVersionNotes(normalizeOptional(request.versionNotes(), ""));
        }
        if ("live".equalsIgnoreCase(qualifier.getStatus()) && qualifier.getPublishedAt() == null) {
            qualifier.setPublishedAt(Instant.now());
        }
    }

    private void validateBeforeSave(Long organizationId, Qualifier qualifier, Long qualifierId, boolean creating) {
        String status = normalizeStatus(qualifier.getStatus());
        qualifier.setStatus(status);
        if ("live".equals(status)) {
            ensureSingleLive(organizationId, qualifierId);
            validatePublishable(qualifier);
            qualifier.setPublishedAt(qualifier.getPublishedAt() != null ? qualifier.getPublishedAt() : Instant.now());
        }
    }

    private void validatePublishable(Qualifier qualifier) {
        if (qualifier.getSystemPrompt() == null || qualifier.getSystemPrompt().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Cannot publish qualifier without system prompt");
        }
        if (qualifier.getFieldSchema() == null || qualifier.getFieldSchema().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Cannot publish qualifier without field schema");
        }
    }

    private void ensureSingleLive(Long organizationId, Long excludeId) {
        boolean exists = excludeId == null
            ? qualifierRepository.existsByOrganizationIdAndStatus(organizationId, "live")
            : qualifierRepository.existsByOrganizationIdAndStatusAndIdNot(organizationId, "live", excludeId);
        if (exists) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Organization already has a live qualifier. Archive it first.");
        }
    }

    private void ensureSlugUnique(Long organizationId, String slug, Long excludeId) {
        boolean exists = excludeId == null
            ? qualifierRepository.existsByOrganizationIdAndSlug(organizationId, slug)
            : qualifierRepository.existsByOrganizationIdAndSlugAndIdNot(organizationId, slug, excludeId);
        if (exists) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Another qualifier already uses that slug");
        }
    }

    private String normalizeName(String value) {
        String normalized = normalizeOptional(value, null);
        if (normalized == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Qualifier name is required");
        }
        return normalized;
    }

    private String normalizeSlug(String value) {
        String normalized = value == null ? "" : value.trim().toLowerCase(Locale.ROOT)
            .replaceAll("[^a-z0-9-]+", "-")
            .replaceAll("-+", "-")
            .replaceAll("^-|-$", "");
        if (normalized.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Qualifier slug is required");
        }
        return normalized;
    }

    private String normalizeStatus(String status) {
        String normalized = normalizeOptional(status, "draft");
        if (!List.of("draft", "live", "archived").contains(normalized)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid qualifier status");
        }
        return normalized;
    }

    private String normalizeOptional(String value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String normalized = value.trim();
        return normalized.isBlank() ? fallback : normalized;
    }

    private Map<String, Object> cleanMap(Map<String, Object> source) {
        if (source == null || source.isEmpty()) {
            return null;
        }
        return new LinkedHashMap<>(source);
    }

    private List<String> cleanStrings(List<String> source) {
        if (source == null) {
            return null;
        }
        List<String> cleaned = new ArrayList<>();
        for (String value : source) {
            String normalized = normalizeOptional(value, null);
            if (normalized != null && !cleaned.contains(normalized)) {
                cleaned.add(normalized);
            }
        }
        return cleaned.isEmpty() ? null : List.copyOf(cleaned);
    }

    public record UpsertRequest(
        String name,
        String slug,
        String status,
        String systemPrompt,
        String assistantStyle,
        String goalDefinition,
        Map<String, Object> fieldSchema,
        List<String> requiredFields,
        Map<String, Object> scoringRules,
        Map<String, Object> bandThresholds,
        Map<String, Object> confidenceThresholds,
        Map<String, Object> takeoverRules,
        Map<String, Object> videoOfferRules,
        Boolean ragEnabled,
        List<String> knowledgeSourceIds,
        Integer maxClarifyingQuestions,
        String contactCapturePolicy,
        Integer version,
        String versionNotes
    ) {
        public boolean containsRuntimeFields() {
            return name != null
                || slug != null
                || systemPrompt != null
                || assistantStyle != null
                || goalDefinition != null
                || fieldSchema != null
                || requiredFields != null
                || scoringRules != null
                || bandThresholds != null
                || confidenceThresholds != null
                || takeoverRules != null
                || videoOfferRules != null
                || ragEnabled != null
                || knowledgeSourceIds != null
                || maxClarifyingQuestions != null
                || contactCapturePolicy != null
                || version != null
                || versionNotes != null;
        }
    }

    public record PublicActiveQualifierResponse(
        String organizationSlug,
        boolean enabled,
        PublicQualifierSummary qualifier
    ) {
    }

    public record PublicQualifierSummary(
        Long id,
        String slug,
        String name,
        String assistantStyle
    ) {
    }
}
