import { Skeleton } from 'antd';

const Loading: React.FC = () => (
  <div className="route-loading" role="status" aria-label="页面加载中">
    <Skeleton active paragraph={{ rows: 8 }} />
  </div>
);

export default Loading;
