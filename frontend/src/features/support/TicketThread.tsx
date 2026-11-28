import { formatDateTime } from "../../lib/format";
import type { TicketMessage } from "./supportLabels";
import "./support.css";

export function TicketThread({ messages }: { messages: TicketMessage[] }) {
  return (
    <ol className="ticket-thread">
      {messages.map(message => (
        <li
          key={message.support_message_id}
          className={
            message.author_kind === "platform" ? "ticket-message is-team" : "ticket-message"
          }
        >
          <header>
            <strong>{message.author_name}</strong>
            <small>{formatDateTime(message.created_at)}</small>
          </header>
          {message.body.split("\n").map((line, index) => (
            <p key={index}>{line}</p>
          ))}
        </li>
      ))}
    </ol>
  );
}
