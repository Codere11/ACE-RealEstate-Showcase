package com.ace.platform.qualifier;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Comparator;
import java.util.List;
import java.util.Map;

@RestController
@Transactional
public class QualifierApiController {

    private final QualifierService qualifierService;
    private final UserRepository userRepository;
    private final OrganizationRepository organizationRepository;

    public QualifierApiController(QualifierService qualifierService, UserRepository userRepository, OrganizationRepository organizationRepository) {
        this.qualifierService = qualifierService;
        this.userRepository = userRepository;
        this.organizationRepository = organizationRepository;
    }

    @GetMapping("/api/public/organizations/{orgSlug}/qualifier-active")
    public QualifierService.PublicActiveQualifierResponse publicActiveQualifier(@PathVariable String orgSlug) {
        Organization organization = organizationRepository.findBySlugAndActiveTrue(orgSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        return qualifierService.publicActiveQualifier(organization);
    }

    @GetMapping("/api/organizations/{orgId}/qualifiers")
    public List<QualifierResponse> qualifiers(@PathVariable Long orgId, @RequestParam(required = false) String status, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return qualifierService.listForOrganization(orgId).stream()
            .filter(item -> status == null || status.isBlank() || item.getStatus().equalsIgnoreCase(status.trim()))
            .sorted(Comparator.comparing(Qualifier::getUpdatedAt).reversed())
            .map(QualifierResponse::from)
            .toList();
    }

    @GetMapping("/api/organizations/{orgId}/qualifiers/active")
    public QualifierResponse activeQualifier(@PathVariable Long orgId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return qualifierService.findActive(orgId)
            .map(QualifierResponse::from)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "No live qualifier found"));
    }

    @GetMapping("/api/organizations/{orgId}/qualifiers/{qualifierId}")
    public QualifierResponse qualifier(@PathVariable Long orgId, @PathVariable Long qualifierId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return QualifierResponse.from(qualifierService.getQualifier(orgId, qualifierId));
    }

    @PostMapping("/api/organizations/{orgId}/qualifiers")
    public QualifierResponse createQualifier(@PathVariable Long orgId, @RequestBody QualifierService.UpsertRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        return QualifierResponse.from(qualifierService.createQualifier(organization, request));
    }

    @PutMapping("/api/organizations/{orgId}/qualifiers/{qualifierId}")
    public QualifierResponse updateQualifier(@PathVariable Long orgId, @PathVariable Long qualifierId, @RequestBody QualifierService.UpsertRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        return QualifierResponse.from(qualifierService.updateQualifier(organization, qualifierId, request));
    }

    @PostMapping("/api/organizations/{orgId}/qualifiers/{qualifierId}/publish")
    public QualifierResponse publishQualifier(@PathVariable Long orgId, @PathVariable Long qualifierId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        return QualifierResponse.from(qualifierService.publish(organization, qualifierId));
    }

    @PostMapping("/api/organizations/{orgId}/qualifiers/{qualifierId}/archive")
    public QualifierResponse archiveQualifier(@PathVariable Long orgId, @PathVariable Long qualifierId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        return QualifierResponse.from(qualifierService.archive(organization, qualifierId));
    }

    private User requireUser(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required");
        }
        return userRepository.findByUsername(authentication.getName())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));
    }

    private void requireOrgAccess(User user, Long orgId) {
        boolean platformAdmin = user.getRole().name().equals("PLATFORM_ADMIN");
        boolean sameOrg = user.getOrganization() != null && orgId.equals(user.getOrganization().getId());
        if (!platformAdmin && !sameOrg) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This user cannot access the requested organization");
        }
    }

    public record QualifierResponse(
        Long id,
        Long organizationId,
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
        boolean ragEnabled,
        List<String> knowledgeSourceIds,
        int maxClarifyingQuestions,
        String contactCapturePolicy,
        int version,
        String versionNotes,
        java.time.Instant createdAt,
        java.time.Instant updatedAt,
        java.time.Instant publishedAt
    ) {
        static QualifierResponse from(Qualifier qualifier) {
            return new QualifierResponse(
                qualifier.getId(),
                qualifier.getOrganization().getId(),
                qualifier.getName(),
                qualifier.getSlug(),
                qualifier.getStatus(),
                qualifier.getSystemPrompt(),
                qualifier.getAssistantStyle(),
                qualifier.getGoalDefinition(),
                qualifier.getFieldSchema(),
                qualifier.getRequiredFields(),
                qualifier.getScoringRules(),
                qualifier.getBandThresholds(),
                qualifier.getConfidenceThresholds(),
                qualifier.getTakeoverRules(),
                qualifier.getVideoOfferRules(),
                qualifier.isRagEnabled(),
                qualifier.getKnowledgeSourceIds(),
                qualifier.getMaxClarifyingQuestions(),
                qualifier.getContactCapturePolicy(),
                qualifier.getVersion(),
                qualifier.getVersionNotes(),
                qualifier.getCreatedAt(),
                qualifier.getUpdatedAt(),
                qualifier.getPublishedAt()
            );
        }
    }
}
