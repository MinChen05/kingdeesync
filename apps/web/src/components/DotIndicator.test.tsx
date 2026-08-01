import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DotIndicator } from './DotIndicator';

describe('DotIndicator', () => {
  it('renders with testid for "ok" level', () => {
    render(<DotIndicator level="ok" />);
    expect(screen.getByTestId('dot-indicator-ok')).toBeInTheDocument();
  });

  it('renders with testid for "error" level', () => {
    render(<DotIndicator level="error" />);
    expect(screen.getByTestId('dot-indicator-error')).toBeInTheDocument();
  });

  it('renders with testid for "unknown" level', () => {
    render(<DotIndicator level="unknown" />);
    expect(screen.getByTestId('dot-indicator-unknown')).toBeInTheDocument();
  });

  it('renders accessibility label for "ok"', () => {
    render(<DotIndicator level="ok" />);
    expect(screen.getByText('正常')).toBeInTheDocument();
  });

  it('renders accessibility label for "error"', () => {
    render(<DotIndicator level="error" />);
    expect(screen.getByText('异常')).toBeInTheDocument();
  });

  it('renders accessibility label for "unknown"', () => {
    render(<DotIndicator level="unknown" />);
    expect(screen.getByText('未知')).toBeInTheDocument();
  });

  it('uses default size of 8px', () => {
    const { container } = render(<DotIndicator level="ok" />);
    const span = container.firstChild as HTMLElement;
    expect(span.style.width).toBe('8px');
    expect(span.style.height).toBe('8px');
  });

  it('respects custom size', () => {
    const { container } = render(<DotIndicator level="ok" size={14} />);
    const span = container.firstChild as HTMLElement;
    expect(span.style.width).toBe('14px');
    expect(span.style.height).toBe('14px');
  });
});
