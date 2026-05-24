import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import Pagination from './Pagination';

const meta: Meta<typeof Pagination> = {
  title: 'Components/Pagination',
  component: Pagination,
  tags: ['autodocs'],
  argTypes: {
    onPageChange: { action: 'pageChanged' },
  },
};

export default meta;
type Story = StoryObj<typeof Pagination>;

export const FirstPage: Story = {
  args: { currentPage: 1, totalPages: 7 },
};

export const MiddlePage: Story = {
  args: { currentPage: 4, totalPages: 7 },
};

export const LastPage: Story = {
  args: { currentPage: 7, totalPages: 7 },
};

export const SinglePage: Story = {
  args: { currentPage: 1, totalPages: 1 },
};

export const ManyPages: Story = {
  args: { currentPage: 50, totalPages: 100 },
};
