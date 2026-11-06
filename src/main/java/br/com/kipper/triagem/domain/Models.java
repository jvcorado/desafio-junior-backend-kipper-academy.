package br.com.kipper.triagem.domain;

import jakarta.validation.constraints.*;
import java.time.Instant;

public final class Models {
    private Models() {}
    public enum Category { BILLING, TECHNICAL, OTHER }
    public enum Priority { NORMAL, HIGH }
    public enum Team { FINANCE, TECHNICAL, REVIEW }
    public enum Status { RECEIVED, PROCESSING, REVIEW, READY, SENDING, FORWARDED, DELIVERY_FAILED, DELIVERY_UNKNOWN, CLOSED }
    public record Event(
        @NotBlank @Size(max=60) @Pattern(regexp="[a-zA-Z0-9_-]+") String source,
        @NotBlank @Size(max=160) String eventId,
        @NotBlank @Size(max=160) String ticketId,
        @NotBlank @Size(max=160) String customerId,
        @NotBlank @Size(max=120) String customerName,
        @NotBlank @Pattern(regexp="\\+[1-9][0-9]{7,14}", message="deve usar E.164, por exemplo +5511999999999") String whatsapp,
        @NotBlank @Size(max=12000) String message,
        @NotNull Instant occurredAt) {}
    public record Ticket(String id, String source, String ticketId, String customerId, String customerName,
        String whatsapp, String message, String occurredAt, String createdAt, String updatedAt,
        Status status, Category category, Priority priority, Team team, String explanation,
        String externalId, String externalUrl, String deliveryAdapter) {}
    public record Policy(String id, Category category, String subject, String rule, Team team, int version, boolean active) {}
    public record PolicyInput(@NotNull Category category, @NotBlank @Size(max=160) String subject,
        @NotBlank @Size(max=3000) String rule, @NotNull Team team, @Min(1) Integer expectedVersion) {}
    public record Proposal(Category category, Priority priority, Team team, String explanation,
        Boolean sufficientInformation, Boolean productUnavailable, String evidence, String policyId, Integer policyVersion) {}
    public record Receipt(String ticketId, String outcome, String conflictId) {}
    public record Resolution(@NotBlank @Size(max=1000) String note,
        @Size(max=160) String newEventId, @Size(max=160) String newTicketId) {}
    public record Note(@NotBlank @Size(max=1000) String note) {}
}
