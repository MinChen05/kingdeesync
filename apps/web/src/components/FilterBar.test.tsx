import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FilterBar } from './FilterBar';

describe('FilterBar', () => {
  it('renders nothing interactive when all props are omitted', () => {
    const { container } = render(<FilterBar />);
    expect(container.querySelector('select')).not.toBeInTheDocument();
    expect(container.querySelector('input')).not.toBeInTheDocument();
  });

  it('renders search input when onSearchChange provided', () => {
    render(
      <FilterBar
        searchValue=""
        onSearchChange={() => {}}
        searchPlaceholder="搜索 run_id"
      />,
    );
    expect(screen.getByPlaceholderText('搜索 run_id')).toBeInTheDocument();
  });

  it('does not render reset button when showReset is false', () => {
    const { container } = render(
      <FilterBar onReset={() => {}} showReset={false} />,
    );
    // Only the wrapper div should be present, no buttons
    expect(container.querySelectorAll('button').length).toBe(0);
  });

  it('renders reset button when showReset is true', () => {
    const { container } = render(
      <FilterBar onReset={() => {}} showReset />,
    );
    expect(container.querySelectorAll('button').length).toBe(1);
  });
});
