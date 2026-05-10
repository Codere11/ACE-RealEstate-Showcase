package com.ace.platform.live;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

@Component
@Profile("!test")
public class LiveKitTokenService {

    private final ObjectMapper objectMapper;
    private final String explicitWsUrl;
    private final String apiKey;
    private final String apiSecret;

    public LiveKitTokenService(
        ObjectMapper objectMapper,
        @Value("${ACE_LIVEKIT_WS_URL:${ace.livekit.ws-url:}}") String explicitWsUrl,
        @Value("${ACE_LIVEKIT_API_KEY:${ace.livekit.api-key:devkey}}") String apiKey,
        @Value("${ACE_LIVEKIT_API_SECRET:${ace.livekit.api-secret:devsecretkey_for_local_livekit_32chars}}") String apiSecret
    ) {
        this.objectMapper = objectMapper;
        this.explicitWsUrl = explicitWsUrl != null ? explicitWsUrl.trim() : "";
        this.apiKey = apiKey;
        this.apiSecret = apiSecret;
    }

    public String resolvedWsUrl(String requestHost, String requestScheme) {
        if (!explicitWsUrl.isBlank()) return explicitWsUrl;
        String host = (requestHost == null || requestHost.isBlank()) ? "127.0.0.1" : requestHost.trim();
        int colon = host.indexOf(':');
        if (colon >= 0) host = host.substring(0, colon);
        String scheme = "https".equalsIgnoreCase(requestScheme) ? "wss" : "ws";
        return scheme + "://" + host + ":7880";
    }

    public String managerToken(String roomName, String identity, String displayName) {
        return buildToken(roomName, identity, displayName, true, false);
    }

    public String visitorToken(String roomName, String identity, String displayName) {
        return buildToken(roomName, identity, displayName, false, true);
    }

    private String buildToken(String roomName, String identity, String displayName, boolean canPublish, boolean canSubscribe) {
        try {
            long now = Instant.now().getEpochSecond();
            Map<String, Object> header = Map.of("alg", "HS256", "typ", "JWT");
            Map<String, Object> video = new LinkedHashMap<>();
            video.put("roomJoin", true);
            video.put("room", roomName);
            video.put("canPublish", canPublish);
            video.put("canSubscribe", canSubscribe);
            video.put("canPublishData", canPublish);

            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("iss", apiKey);
            payload.put("sub", identity);
            payload.put("nbf", now - 5);
            payload.put("exp", now + 3600);
            payload.put("name", displayName);
            payload.put("video", video);

            String encodedHeader = base64Url(objectMapper.writeValueAsBytes(header));
            String encodedPayload = base64Url(objectMapper.writeValueAsBytes(payload));
            String signingInput = encodedHeader + "." + encodedPayload;
            return signingInput + "." + sign(signingInput);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to build LiveKit token", ex);
        }
    }

    private String sign(String input) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(apiSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return base64Url(mac.doFinal(input.getBytes(StandardCharsets.UTF_8)));
    }

    private String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
