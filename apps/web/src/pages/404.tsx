import { useNavigate } from '@umijs/max';
import { Button, Result } from 'antd';
import React from 'react';

const Page404: React.FC = () => {
  const navigate = useNavigate();
  return (
    <Result
      status="404"
      title="404"
      subTitle="找不到该页面"
      extra={
        <Button type="primary" onClick={() => navigate('/overview')}>
          返回首页
        </Button>
      }
    />
  );
};
export default Page404;
