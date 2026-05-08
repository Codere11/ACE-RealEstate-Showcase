package com.ace.platform.auth;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

@Component
public class AceJwtService {

    private final ObjectMapper objectMapper;
    private final String secret;
    private final long expireMinutes;

    public AceJwtService(
        ObjectMapper objectMapper,
        @Value("${ACE_SECRET:${ace.secret:dev-secret-change-me}}") String secret,
        @Value("${ACE_JWT_EXPIRE_MIN:${ace.jwt-expire-min:1440}}") long expireMinutes
    ) {
        this.objectMapper = objectMapper;
        this.secret = secret;
        this.expireMinutes = expireMinutes;
    }

    public String createToken(Map<String, Object> payload) {
        try {
            long now = Instant.now().getEpochSecond();
            Map<String, Object> header = Map.of("alg", "HS256", "typ", "JWT");
            Map<String, Object> claims = new LinkedHashMap<>(payload != null ? payload : Map.of());
            claims.put("iat", now);
            claims.put("exp", now + (expireMinutes * 60));
            String encodedHeader = Base64.getUrlEncoder().withoutPadding().encodeToString(objectMapper.writeValueAsBytes(header));
            String encodedPayload = Base64.getUrlEncoder().withoutPadding().encodeToString(objectMapper.writeValueAsBytes(claims));
            String signingInput = encodedHeader + "." + encodedPayload;
            return signingInput + "." + sign(signingInput);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to create ACE JWT", ex);
        }
    }

    public Optional<Map<String, Object>> verify(String token) {
        try {
            if (token == null || token.isBlank()) return Optional.empty();
            String[] parts = token.split("\\.");
            if (parts.length != 3) return Optional.empty();

            String signingInput = parts[0] + "." + parts[1];
            String expectedSignature = sign(signingInput);
            if (!constantTimeEquals(expectedSignature, parts[2])) return Optional.empty();

            byte[] payloadBytes = Base64.getUrlDecoder().decode(parts[1]);
            Map<String, Object> claims = objectMapper.readValue(payloadBytes, new TypeReference<>() {});
            if (isExpired(claims)) return Optional.empty();
            return Optional.of(claims);
        } catch (Exception ex) {
            return Optional.empty();
        }
    }

    private boolean isExpired(Map<String, Object> claims) {
        Object exp = claims.get("exp");
        if (exp instanceof Number number) {
            return Instant.now().getEpochSecond() >= number.longValue();
        }
        return false;
    }

    private String sign(String input) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return Base64.getUrlEncoder().withoutPadding().encodeToString(mac.doFinal(input.getBytes(StandardCharsets.UTF_8)));
    }

    private boolean constantTimeEquals(String left, String right) {
        if (left == null || right == null) return false;
        byte[] a = left.getBytes(StandardCharsets.UTF_8);
        byte[] b = right.getBytes(StandardCharsets.UTF_8);
        if (a.length != b.length) return false;
        int result = 0;
        for (int i = 0; i < a.length; i++) result |= a[i] ^ b[i];
        return result == 0;
    }
}
