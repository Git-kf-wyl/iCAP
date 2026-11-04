export function getErrorMessage(error) {
    // 如果是网络错误或请求被取消等，没有 response 对象
    if (!error.response) {
      if (error.message === 'Network Error') {
        return '网络连接异常，请检查您的网络。';
      }
      return '请求发送失败，请稍后重试。';
    }
  
    const { status, data } = error.response;
    // 这里可以根据后端返回的特定字段和状态码进行定制
    if (data && data.res) {
      return data.res; // 假设您后端统一用 res 字段返回错误信息
    }
    if (data && data.message) {
      return data.message;
    }
  
    // 如果都没有，返回通用的 HTTP 状态码信息
    switch (status) {
      case 400:
        return '请求参数错误';
      case 401:
        return '未授权，请登录';
      case 403:
        return '拒绝访问';
      case 404:
        return '请求的资源不存在';
      case 500:
        return '服务器内部错误';
      default:
        return `请求失败，状态码: ${status}`;
    }
  }