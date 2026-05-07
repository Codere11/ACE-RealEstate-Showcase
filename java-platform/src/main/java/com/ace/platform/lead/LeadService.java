package com.ace.platform.lead;

import com.ace.platform.organization.Organization;
import com.ace.platform.user.User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
public class LeadService {

    private final LeadRepository leadRepository;

    public LeadService(LeadRepository leadRepository) {
        this.leadRepository = leadRepository;
    }

    @Transactional
    public Lead getOrCreateLead(Organization organization, String sid, String surveySlug) {
        String effectiveSid = (sid == null || sid.isBlank()) ? newSid() : sid.trim();
        return leadRepository.findByOrganizationIdAndSid(organization.getId(), effectiveSid)
            .orElseGet(() -> leadRepository.save(new Lead(
                organization,
                effectiveSid,
                "Visitor " + effectiveSid.substring(Math.max(0, effectiveSid.length() - 6)),
                surveySlug
            )));
    }

    @Transactional(readOnly = true)
    public Optional<Lead> findByOrganizationAndSid(Long organizationId, String sid) {
        if (sid == null || sid.isBlank()) {
            return Optional.empty();
        }
        return leadRepository.findByOrganizationIdAndSid(organizationId, sid.trim());
    }

    @Transactional(readOnly = true)
    public List<Lead> listForOrganization(Long organizationId) {
        return leadRepository.findByOrganizationIdOrderByLastMessageAtDescCreatedAtDesc(organizationId);
    }

    @Transactional
    public Lead touchLead(Lead lead, String preview) {
        lead.setLastMessagePreview(truncate(preview, 500));
        lead.setLastMessageAt(Instant.now());
        return leadRepository.save(lead);
    }

    @Transactional
    public Lead updateSurveyProgress(Lead lead, int progress) {
        lead.setSurveyProgress(Math.max(0, Math.min(progress, 100)));
        if (lead.getSurveyProgress() >= 100 && lead.getStatus() == LeadStatus.SURVEY) {
            lead.setStatus(LeadStatus.OPEN_CHAT);
        }
        return leadRepository.save(lead);
    }

    @Transactional
    public Lead activateTakeover(Lead lead, User user) {
        lead.setTakeoverActive(true);
        lead.setStatus(LeadStatus.HUMAN_TAKEOVER);
        lead.setAssignedUser(user);
        lead.setLastMessageAt(Instant.now());
        return leadRepository.save(lead);
    }

    @Transactional
    public Lead endTakeover(Lead lead) {
        lead.setTakeoverActive(false);
        lead.setStatus(LeadStatus.OPEN_CHAT);
        return leadRepository.save(lead);
    }

    @Transactional
    public Lead captureContactHints(Lead lead, String message) {
        if (message == null || message.isBlank()) {
            return lead;
        }
        String email = extractEmail(message);
        String phone = extractPhone(message);
        if (email != null) {
            lead.setEmail(email);
        }
        if (phone != null) {
            lead.setPhone(phone);
        }
        return leadRepository.save(lead);
    }

    @Transactional
    public void deleteLead(Lead lead) {
        leadRepository.delete(lead);
    }

    private String truncate(String text, int max) {
        if (text == null) {
            return null;
        }
        return text.length() <= max ? text : text.substring(0, max - 1);
    }

    private String extractEmail(String text) {
        String[] parts = text.split("\\s+");
        for (String part : parts) {
            String candidate = part.trim().replaceAll("^[<()\\[\\]{}]+|[>),.;:\\]\\[{}]+$", "");
            if (candidate.matches("^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+$")) {
                return candidate.toLowerCase();
            }
        }
        return null;
    }

    private String extractPhone(String text) {
        String digits = text.replaceAll("[^0-9+]", "");
        if (digits.matches("^\\+?[0-9]{7,15}$")) {
            return digits;
        }
        return null;
    }

    public String newSid() {
        return "sid_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
    }
}
