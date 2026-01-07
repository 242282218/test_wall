interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Something went wrong",
  description = "Please try again in a moment.",
  onRetry
}: ErrorStateProps) {
  return (
    <div className="state state--error">
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {onRetry ? (
        <button className="button button--ghost" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}