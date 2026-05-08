package com.ace.platform.live;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

@Deprecated(since = "java-live-cutover")
@Component
public class PythonLiveSessionClient {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String baseUrl;

    public PythonLiveSessionClient(ObjectMapper objectMapper, @Value("${ace.python-backend-url:http://127.0.0.1:8000}") String baseUrl) {
        this.httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
        this.objectMapper = objectMapper;
        this.baseUrl = baseUrl != null ? baseUrl.replaceAll("/+$", "") : "http://127.0.0.1:8000";
    }

    public LiveSessionResponse current(InternalLiveSessionRequest request) {
        return post("/api/internal/live-sessions/current", request, LiveSessionResponse.class);
    }

    public LiveSessionResponse preview(InternalLiveSessionRequest request) {
        return post("/api/internal/live-sessions/preview", request, LiveSessionResponse.class);
    }

    public LiveSessionResponse goLive(InternalLiveSessionRequest request) {
        return post("/api/internal/live-sessions/go-live", request, LiveSessionResponse.class);
    }

    public LiveSessionResponse end(InternalLiveSessionEndRequest request) {
        return post("/api/internal/live-sessions/end", request, LiveSessionResponse.class);
    }

    public PublicLiveSessionResponse publicState(Long organizationId, String sid) {
        try {
            HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/api/internal/live-sessions/public/" + organizationId + "?sid=" + encode(sid)))
                .timeout(Duration.ofSeconds(20))
                .GET()
                .build();
            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("Python public live-session returned status " + response.statusCode() + ": " + response.body());
            }
            return objectMapper.readValue(response.body(), PublicLiveSessionResponse.class);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to load public live-session state", ex);
        }
    }

    private <T> T post(String path, Object payload, Class<T> responseType) {
        try {
            String body = objectMapper.writeValueAsString(payload);
            HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 404 && responseType.equals(LiveSessionResponse.class) && "null".equals(response.body())) {
                return null;
            }
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("Python live-session returned status " + response.statusCode() + ": " + response.body());
            }
            if (response.body() == null || response.body().isBlank() || "null".equals(response.body().trim())) {
                return null;
            }
            return objectMapper.readValue(response.body(), responseType);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to call Python live-session service", ex);
        }
    }

    private String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    public record InternalLiveSessionRequest(
        @JsonProperty("organization_id") Long organizationId,
        String sid,
        @JsonProperty("manager_user_id") Long managerUserId,
        @JsonProperty("manager_display_name") String managerDisplayName
    ) {
    }

    public record InternalLiveSessionEndRequest(
        @JsonProperty("organization_id") Long organizationId,
        @JsonProperty("session_id") Long sessionId,
        @JsonProperty("manager_display_name") String managerDisplayName
    ) {
    }

    public record LiveSessionResponse(
        Long id,
        @JsonProperty("organization_id") Long organizationId,
        String sid,
        @JsonProperty("manager_user_id") Long managerUserId,
        @JsonProperty("manager_display_name") String managerDisplayName,
        String provider,
        String status,
        @JsonProperty("room_name") String roomName,
        @JsonProperty("stage_message") String stageMessage,
        @JsonProperty("ws_url") String wsUrl,
        String token,
        @JsonProperty("started_at") String startedAt,
        @JsonProperty("live_at") String liveAt,
        @JsonProperty("ended_at") String endedAt,
        @JsonProperty("created_at") String createdAt,
        @JsonProperty("updated_at") String updatedAt
    ) {
    }

    public record PublicLiveSessionResponse(
        String sid,
        String status,
        @JsonProperty("manager_display_name") String managerDisplayName,
        @JsonProperty("room_name") String roomName,
        @JsonProperty("stage_message") String stageMessage,
        @JsonProperty("live_at") String liveAt,
        @JsonProperty("ended_at") String endedAt,
        @JsonProperty("ws_url") String wsUrl,
        String token
    ) {
    }
}
