import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

import { logAppError } from "@/lib/app-logger";
import { PageErrorState } from "@/components/ui/page-error-state";

type ErrorBoundaryProps = {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  resetKey?: string | number;
};

type ErrorBoundaryState = {
  error: Error | null;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    error: null,
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    logAppError("react.error-boundary", "Captured a render error.", error, {
      componentStack: errorInfo.componentStack,
    });
    this.props.onError?.(error, errorInfo);
  }

  componentDidUpdate(previousProps: ErrorBoundaryProps) {
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.reset();
    }
  }

  private readonly reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback;
    }

    return (
      <PageErrorState
        title="This page hit a rendering problem"
        description="A refresh usually clears temporary startup or rendering issues. If the API is also down, the page will recover once the backend responds again."
        detail={this.state.error?.message ?? null}
        onRetry={this.reset}
      />
    );
  }
}
